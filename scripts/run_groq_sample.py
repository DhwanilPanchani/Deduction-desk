"""Script to run a small test of 10 LLM-escalated deductions using Groq."""

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

# Load agent/.env explicitly
load_dotenv(ROOT / "agent" / ".env")

import psycopg2
from psycopg2.extras import RealDictCursor

from agent.confidence import build_decision
from agent.config import Settings
from agent.llm_classifier import LLMClassifier
from agent.llm_provider import GroqProvider
from agent.models import Deduction
from agent.rules_engine import RulesEngine


def main() -> None:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        print("ERROR: GROQ_API_KEY environment variable is not set.", file=sys.stderr)
        print("Please provide GROQ_API_KEY in agent/.env file.", file=sys.stderr)
        sys.exit(1)

    # Key loading confirmation without leaking secret
    key_masked = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
    print("=" * 80)
    print("GROQ API KEY CONFIGURATION CONFIRMATION")
    print("=" * 80)
    print(f"GROQ_API_KEY successfully loaded: YES")
    print(f"Key format / length:             {len(api_key)} characters (prefix: {api_key[:4]}, suffix: {api_key[-4:]})")
    model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    print(f"Target model:                    {model}")
    print(f"Rate limit setting:              2.6s min interval (~23 RPM, safely under 30 RPM)")
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
                   d.retailer_notes, d.invoice_id,
                   gt.is_valid AS gt_is_valid, gt.true_reason AS gt_reason
            FROM deductions d
            JOIN invoices i ON i.id = d.invoice_id
            JOIN purchase_orders po ON po.id = i.purchase_order_id
            JOIN retailers r ON r.id = po.retailer_id
            JOIN agent_decisions ad ON ad.deduction_id = d.id
            JOIN ground_truth gt ON gt.deduction_id = d.id
            WHERE ad.method = 'llm'
            ORDER BY d.id
            LIMIT 10
            """
        )
        sample_rows = cur.fetchall()

    print(f"Loaded {len(sample_rows)} LLM-escalated deductions from the database.\n")
    print("Beginning 10-case evaluation (3 self-consistency calls per deduction)...")

    start_time = time.monotonic()
    results = []

    for index, row in enumerate(sample_rows, 1):
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

        rule_result = rules.evaluate(deduction)
        t_case_start = time.monotonic()
        llm_result = classifier.classify(deduction, rule_result.context)
        case_duration = time.monotonic() - t_case_start

        decision = build_decision(deduction, rule_result, llm_result, config)

        results.append(
            {
                "index": index,
                "deduction": deduction,
                "row": row,
                "llm_result": llm_result,
                "decision": decision,
                "duration": case_duration,
            }
        )
        print(f"[{index:02d}/10] Deduction #{deduction.id} ({deduction.type:<11}) done in {case_duration:.2f}s | agreement: {llm_result.agreement_rate:.0%} | calls so far: {provider.call_count}")

    total_time = time.monotonic() - start_time
    total_calls = provider.call_count
    classifier.close()
    rules.close()
    conn.close()

    print("\n" + "=" * 80)
    print("DETAILED RESULTS FOR 10 SAMPLE DEDUCTIONS (GROQ QWEN/QWEN3.8-27B)")
    print("=" * 80 + "\n")

    for item in results:
        d: Deduction = item["deduction"]
        row = item["row"]
        llm = item["llm_result"]
        dec = item["decision"]

        verdict_str = "valid/accept" if dec.is_valid else "invalid/dispute"
        gt_str = "valid" if row["gt_is_valid"] else "invalid"
        agreement_pct = llm.agreement_rate * 100
        conf_pct = dec.confidence * 100

        print(f"### {item['index']}. Deduction {d.id} — {d.type} / email-style")
        print(f"- Confidence: {conf_pct:.2f}% (capped from {agreement_pct:.1f}% agreement rate)")
        print(f"- 3-call agreement: {agreement_pct:.1f}% (votes: {llm.votes})")
        print(f"- Final verdict: {verdict_str}; ground truth: {gt_str}")
        print(f"- Needs human review: {dec.needs_human_review}")
        print(f"- Retailer notes: {d.retailer_notes}")
        print(f"- Agent reasoning: {dec.reasoning}")
        print(f"- Ground-truth reason: {row['gt_reason']}")
        print("- Raw individual responses:")
        for call_idx, raw_envelope in enumerate(llm.raw_responses, 1):
            try:
                env = json.loads(raw_envelope)
                resp_payload = json.loads(env.get("response", "{}"))
                print(f"    Vote {call_idx}: is_valid={resp_payload.get('is_valid')} | reasoning: {resp_payload.get('reasoning')}")
            except Exception:
                print(f"    Vote {call_idx}: {raw_envelope[:120]}")
        print()

    print("=" * 80)
    print("EXECUTION SUMMARY & RATE-LIMIT AUDIT")
    print("=" * 80)
    print(f"Total deductions tested:     {len(results)}")
    print(f"Total API calls made:        {total_calls}")
    expected_calls = len(results) * 3
    if total_calls == expected_calls:
        print(f"Call count verification:     EXACT MATCH ({total_calls} calls = {len(results)} cases × 3 votes, 0 retries needed)")
    else:
        print(f"Call count verification:     {total_calls} calls (expected {expected_calls}, {total_calls - expected_calls} retries occurred)")
    print(f"Calls under 30 confirmation: {'CONFIRMED (<= 30 calls)' if total_calls <= 30 else 'EXCEEDED'}")
    print(f"Total runtime:               {total_time:.2f} seconds ({total_time / 60:.2f} minutes)")
    avg_per_case = total_time / len(results) if results else 0
    print(f"Average time per case:       {avg_per_case:.2f} seconds")
    avg_per_call = total_time / total_calls if total_calls else 0
    print(f"Average time per call:       {avg_per_call:.2f} seconds")
    full_batch_cases = 263
    full_batch_calls = full_batch_cases * 3
    est_full_batch_sec = avg_per_case * full_batch_cases
    print(f"\nFull-batch estimation ({full_batch_cases} LLM cases = {full_batch_calls} API calls):")
    print(f"  Estimated runtime:         ~{est_full_batch_sec:.1f} seconds (~{est_full_batch_sec / 60:.1f} minutes)")
    print(f"  Daily request limit check: {full_batch_calls} calls fits safely within Groq's 1,000 requests/day free tier")
    print("=" * 80)


if __name__ == "__main__":
    main()
