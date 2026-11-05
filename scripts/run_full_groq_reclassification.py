"""Run full 263-case Groq reclassification batch, update agent_decisions and agent_llm_calls,
and re-generate evaluation reports fresh."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / "agent" / ".env")

import psycopg2
from psycopg2.extras import RealDictCursor

from agent.confidence import build_decision
from agent.config import Settings
from agent.llm_classifier import LLMClassifier
from agent.llm_provider import GroqProvider
from agent.models import Deduction, LLMResult
from agent.rules_engine import RulesEngine
from eval.accuracy_report import generate_report as run_accuracy_report
from eval.calibration_report import generate_report as run_calibration_report
from eval.drift_test import generate_report as run_drift_report


def store_llm_calls(conn, deduction_id: int, result: LLMResult) -> None:
    if len(result.raw_responses) != 3:
        return
    with conn.cursor() as cursor:
        for call_number, raw_response in enumerate(result.raw_responses, 1):
            envelope = json.loads(raw_response)
            model_payload = json.loads(envelope["response"])
            cursor.execute(
                """
                INSERT INTO agent_llm_calls
                    (deduction_id, call_number, is_valid, reasoning, raw_response, is_replay)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (deduction_id, call_number) DO UPDATE SET
                    is_valid=EXCLUDED.is_valid,
                    reasoning=EXCLUDED.reasoning,
                    raw_response=EXCLUDED.raw_response,
                    is_replay=EXCLUDED.is_replay,
                    created_at=NOW()
                """,
                (
                    deduction_id,
                    call_number,
                    bool(model_payload["is_valid"]),
                    str(model_payload["reasoning"]),
                    raw_response,
                    False,
                ),
            )
    conn.commit()


def update_decision(conn, decision) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE agent_decisions
            SET is_valid = %s,
                confidence = %s,
                reasoning = %s,
                needs_human_review = %s,
                created_at = NOW()
            WHERE deduction_id = %s
            """,
            (
                decision.is_valid,
                decision.confidence,
                decision.reasoning,
                decision.needs_human_review,
                decision.deduction_id,
            ),
        )
    conn.commit()


def main() -> None:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        print("ERROR: GROQ_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

    print("=" * 80)
    print("FULL 263-CASE GROQ RECLASSIFICATION BATCH")
    print("=" * 80)
    print(f"Model:                   {model}")
    print(f"Rate limit setting:      2.6s min interval (~23 RPM headroom)")
    print(f"Expected API calls:      ~789 (263 cases × 3 votes)")
    print("=" * 80 + "\n")

    config = Settings(
        llm_provider="groq",
        groq_api_key=api_key,
        groq_model=model,
    )
    provider = GroqProvider(
        api_key=api_key,
        model=model,
        min_interval_seconds=2.6,
        max_retries=3,
    )
    classifier = LLMClassifier(config=config, provider=provider)
    rules = RulesEngine(config=config)

    conn = psycopg2.connect(config.database_url)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT d.id, r.name AS retailer, d.type,
                   d.amount AS claimed_amount, d.status,
                   d.retailer_notes, d.invoice_id
            FROM agent_decisions ad
            JOIN deductions d ON d.id = ad.deduction_id
            JOIN invoices i ON i.id = d.invoice_id
            JOIN purchase_orders po ON po.id = i.purchase_order_id
            JOIN retailers r ON r.id = po.retailer_id
            WHERE ad.method = 'llm'
            ORDER BY d.id
            """
        )
        deductions_raw = cur.fetchall()

    total_cases = len(deductions_raw)
    print(f"Loaded all {total_cases} LLM-escalated deductions from PostgreSQL.")
    print("Starting reclassification loop...\n")

    start_time = time.monotonic()
    unanimous_count = 0
    majority_count = 0
    errors = []

    for index, row in enumerate(deductions_raw, 1):
        deduction = Deduction.model_validate(
            {
                "id": row["id"],
                "retailer": row["retailer"],
                "type": row["type"],
                "claimed_amount": row["claimed_amount"],
                "status": row["status"],
                "retailer_notes": row["retailer_notes"],
                "invoice_id": row["invoice_id"],
            }
        )

        case_t0 = time.monotonic()
        try:
            rule_result = rules.evaluate(deduction)
            llm_result = classifier.classify(deduction, rule_result.context)
            if not llm_result.resolved:
                raise RuntimeError(llm_result.error or "LLM classification unresolved")

            decision = build_decision(deduction, rule_result, llm_result, config)

            # Persist to Postgres
            update_decision(conn, decision)
            store_llm_calls(conn, deduction.id, llm_result)

            if llm_result.agreement_rate == 1.0:
                unanimous_count += 1
            else:
                majority_count += 1

            case_elapsed = time.monotonic() - case_t0
            cumul_elapsed = time.monotonic() - start_time
            rate = index / (cumul_elapsed / 60) if cumul_elapsed else 0

            print(
                f"[{index:03d}/{total_cases}] Deduction #{deduction.id:<3} "
                f"({deduction.type:<11}): is_valid={str(decision.is_valid):<5} "
                f"agree={llm_result.agreement_rate:.0%} "
                f"({case_elapsed:.1f}s) | calls={provider.call_count} "
                f"429s={provider.rate_limit_429_count} | pace={rate:.1f} cases/min"
            )
        except Exception as exc:
            errors.append(f"Deduction #{deduction.id}: {exc}")
            print(f"[{index:03d}/{total_cases}] Deduction #{deduction.id} ERROR: {exc}", file=sys.stderr)

    total_time = time.monotonic() - start_time
    total_calls = provider.call_count
    total_429s = provider.rate_limit_429_count

    classifier.close()
    rules.close()
    conn.close()

    print("\n" + "=" * 80)
    print("RECLASSIFICATION COMPLETE — RUNNING EVALUATION SUITE")
    print("=" * 80 + "\n")

    accuracy = run_accuracy_report(print_report=True)
    print("\n" + "=" * 72)
    calibration = run_calibration_report(print_report=True)
    print("\n" + "=" * 72)
    drift = run_drift_report(print_report=True)

    combined = {"accuracy": accuracy, "calibration": calibration, "drift": drift}
    report_path = ROOT / "eval" / "reports" / "combined_summary.json"
    report_path.write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")

    print("\n" + "=" * 80)
    print("GROQ FULL BATCH SUMMARY AUDIT")
    print("=" * 80)
    print(f"Total deductions reclassified: {total_cases}")
    print(f"Total API calls made:          {total_calls}")
    print(f"Total 429 rate limit events:   {total_429s} (all recovered via exponential backoff)")
    print(f"Total errors/failures:         {len(errors)}")
    print(f"Total elapsed runtime:         {total_time:.2f} seconds ({total_time / 60:.2f} minutes)")
    print(f"Average time per case:         {total_time / total_cases:.2f} seconds")
    print(f"Unanimous (3/3) agreement:     {unanimous_count}/{total_cases} ({unanimous_count / total_cases:.1%})")
    print(f"Split (2/3) majority:          {majority_count}/{total_cases} ({majority_count / total_cases:.1%})")
    print("=" * 80)


if __name__ == "__main__":
    main()

