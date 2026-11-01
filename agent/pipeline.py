"""End-to-end deduction classification pipeline."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import json
from statistics import mean

import psycopg2

from .confidence import build_decision
from .config import Settings, settings
from .llm_classifier import LLMClassifier
from .models import AgentDecision, Deduction, LLMResult
from .portal_client import PortalClient
from .rules_engine import RulesEngine

AGENT_DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS agent_decisions (
    id BIGSERIAL PRIMARY KEY,
    deduction_id BIGINT NOT NULL UNIQUE REFERENCES deductions(id) ON DELETE CASCADE,
    is_valid BOOLEAN NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    reasoning TEXT NOT NULL,
    method TEXT NOT NULL CHECK (method IN ('rules', 'llm', 'escalated')),
    needs_human_review BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

AGENT_LLM_CALLS_DDL = """
CREATE TABLE IF NOT EXISTS agent_llm_calls (
    id BIGSERIAL PRIMARY KEY,
    deduction_id BIGINT NOT NULL REFERENCES deductions(id) ON DELETE CASCADE,
    call_number INTEGER NOT NULL CHECK (call_number BETWEEN 1 AND 3),
    is_valid BOOLEAN NOT NULL,
    reasoning TEXT NOT NULL,
    raw_response TEXT,
    is_replay BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (deduction_id, call_number)
)
"""

UPSERT_DECISION = """
INSERT INTO agent_decisions
    (deduction_id, is_valid, confidence, reasoning, method, needs_human_review)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (deduction_id) DO UPDATE SET
    is_valid = EXCLUDED.is_valid,
    confidence = EXCLUDED.confidence,
    reasoning = EXCLUDED.reasoning,
    method = EXCLUDED.method,
    needs_human_review = EXCLUDED.needs_human_review,
    created_at = NOW()
"""


@dataclass
class PipelineSummary:
    total: int = 0
    rules_resolved: int = 0
    llm_needed: int = 0
    llm_resolved: int = 0
    human_review: int = 0
    method_confidences: dict[str, list[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    errors: list[str] = field(default_factory=list)

    def print(self) -> None:
        def percentage(count: int) -> float:
            return count / self.total * 100 if self.total else 0

        print("\nDeductionDesk agent summary")
        print("=" * 32)
        print(f"Total processed:          {self.total}")
        print(
            f"Rules-resolved:           {self.rules_resolved} ({percentage(self.rules_resolved):.1f}%)"
        )
        print(f"Needed LLM:               {self.llm_needed} ({percentage(self.llm_needed):.1f}%)")
        print(f"LLM-resolved:             {self.llm_resolved} ({percentage(self.llm_resolved):.1f}%)")
        print(f"Human review:             {self.human_review} ({percentage(self.human_review):.1f}%)")
        print("Average confidence by method:")
        for method in ("rules", "llm", "escalated"):
            values = self.method_confidences.get(method, [])
            print(f"  {method:<10} {mean(values):.3f}" if values else f"  {method:<10} n/a")
        print(f"Errors:                   {len(self.errors)}")
        for error in self.errors[:10]:
            print(f"  - {error}")
        if len(self.errors) > 10:
            print(f"  ... and {len(self.errors) - 10} more")


class DeductionPipeline:
    def __init__(self, config: Settings = settings) -> None:
        self.config = config
        self.portal = PortalClient(config)
        self.rules = RulesEngine(config)
        self.llm = LLMClassifier(config)
        self.connection = psycopg2.connect(config.database_url)
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute(AGENT_DECISIONS_DDL)
            cursor.execute(AGENT_LLM_CALLS_DDL)

    def _store(self, decision: AgentDecision) -> None:
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute(
                UPSERT_DECISION,
                (
                    decision.deduction_id,
                    decision.is_valid,
                    decision.confidence,
                    decision.reasoning,
                    decision.method,
                    decision.needs_human_review,
                ),
            )

    def _store_llm_calls(
        self, deduction_id: int, result: LLMResult, *, is_replay: bool = False
    ) -> None:
        """Persist each self-consistency vote, including Ollama's unparsed envelope."""
        if len(result.raw_responses) != 3:
            return
        with self.connection, self.connection.cursor() as cursor:
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
                        is_replay,
                    ),
                )

    def replay_review_traces(self) -> tuple[int, list[str]]:
        """Regenerate transparent vote traces for legacy review candidates.

        Phase 3 did not persist its original raw calls, so these are explicitly
        marked as replays and never change the saved agent decision.
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.id, r.name AS retailer, d.type,
                       d.amount AS claimed_amount, d.status,
                       d.retailer_notes, d.invoice_id
                FROM agent_decisions ad
                JOIN deductions d ON d.id=ad.deduction_id
                JOIN invoices i ON i.id=d.invoice_id
                JOIN purchase_orders po ON po.id=i.purchase_order_id
                JOIN retailers r ON r.id=po.retailer_id
                LEFT JOIN disputes dp ON dp.deduction_id=d.id
                LEFT JOIN human_reviews hr ON hr.deduction_id=d.id
                WHERE ad.needs_human_review=TRUE
                  AND ad.is_valid=FALSE
                  AND dp.id IS NULL
                  AND hr.id IS NULL
                ORDER BY d.id
                """
            )
            columns = [description.name for description in cursor.description]
            deductions = [Deduction.model_validate(dict(zip(columns, row))) for row in cursor.fetchall()]

        errors: list[str] = []
        for index, deduction in enumerate(deductions, 1):
            try:
                rules = self.rules.evaluate(deduction)
                result = self.llm.classify(deduction, rules.context)
                if not result.resolved:
                    raise RuntimeError(result.error or "Ollama returned no usable result")
                self._store_llm_calls(deduction.id, result, is_replay=True)
                print(f"Replayed LLM trace {index}/{len(deductions)} for deduction {deduction.id}")
            except Exception as exc:
                errors.append(f"deduction {deduction.id}: {type(exc).__name__}: {exc}")
        return len(deductions) - len(errors), errors

    def run(self, *, limit: int | None = None, status: str = "pending") -> PipelineSummary:
        deductions = self.portal.fetch_deductions(status=status, limit=limit)
        summary = PipelineSummary()
        total = len(deductions)
        print(f"Fetched {total} {status} deductions from the portal.")

        for index, deduction in enumerate(deductions, 1):
            try:
                rule_result = self.rules.evaluate(deduction)
                llm_result = None
                if rule_result.resolved:
                    summary.rules_resolved += 1
                else:
                    summary.llm_needed += 1
                    llm_result = self.llm.classify(deduction, rule_result.context)
                    if llm_result.resolved:
                        summary.llm_resolved += 1
                    elif llm_result.error:
                        summary.errors.append(
                            f"deduction {deduction.id} Ollama: {llm_result.error}"
                        )

                decision = build_decision(deduction, rule_result, llm_result, self.config)
                self._store(decision)
                if llm_result is not None and llm_result.resolved:
                    self._store_llm_calls(deduction.id, llm_result)
                summary.total += 1
                summary.human_review += int(decision.needs_human_review)
                summary.method_confidences[decision.method].append(decision.confidence)
            except Exception as exc:  # Continue the batch while reporting row-level failures.
                summary.errors.append(f"deduction {deduction.id}: {type(exc).__name__}: {exc}")

            print(
                f"Processed {index}/{total} | rules={summary.rules_resolved} "
                f"llm={summary.llm_resolved} review={summary.human_review} errors={len(summary.errors)}"
            )

        return summary

    def close(self) -> None:
        self.portal.close()
        self.rules.close()
        self.llm.close()
        self.connection.close()
