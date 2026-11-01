"""Ollama-backed classifier for deductions with ambiguous retailer notes."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from typing import Any

import requests
from pydantic import BaseModel, Field, ValidationError

from .config import Settings, settings
from .models import Deduction, LLMResult
from policy import COMPLIANCE_LATE_ALLOWANCE_DAYS


class _OllamaDecision(BaseModel):
    is_valid: bool
    confidence: float | None = Field(default=None, ge=0, le=1)
    reasoning: str = Field(min_length=1)


def _extract_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("response contained no JSON object")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("response JSON was not an object")
    return value


class LLMClassifier:
    def __init__(self, config: Settings = settings, timeout: float = 90.0) -> None:
        self.config = config
        self.timeout = timeout
        self.session = requests.Session()

    def _relevant_context(
        self, deduction: Deduction, context: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Expose only facts relevant to the current deduction category."""
        if deduction.type == "compliance":
            expected = date.fromisoformat(str(context["expected_delivery_date"]))
            delivered = date.fromisoformat(str(context["delivery_date"]))
            days_late = (delivered - expected).days
            allowance_days = COMPLIANCE_LATE_ALLOWANCE_DAYS
            return (
                {
                    "expected_delivery_date": expected.isoformat(),
                    "actual_delivery_date": delivered.isoformat(),
                    "days_late": days_late,
                    "configured_delivery_allowance_days": allowance_days,
                    "delivery_outside_allowance": days_late > allowance_days,
                    "evidence_supports_claim": days_late > allowance_days,
                },
                "Use delivery timing only. Ignore amount, quantity, and price.",
            )
        if deduction.type == "shortage":
            invoiced = int(context["invoiced_qty"])
            delivered = int(context["delivered_qty"])
            return (
                {
                    "claimed_short_qty": context.get("claimed_qty"),
                    "invoiced_qty": invoiced,
                    "delivered_qty": delivered,
                    "actual_short_qty": max(0, invoiced - delivered),
                    "evidence_supports_claim": (
                        context.get("claimed_qty") is not None
                        and int(context["claimed_qty"]) == max(0, invoiced - delivered)
                        and max(0, invoiced - delivered) > 0
                    ),
                },
                "Use only the claimed and actual shortage quantities.",
            )
        if deduction.type == "promotional":
            matched = bool(context.get("matching_promo"))
            return (
                {
                    "matching_authorized_promotion": matched,
                    "product_sku": context.get("product_sku"),
                    "invoice_date": context.get("invoice_date"),
                    "evidence_supports_claim": matched,
                },
                "Use only whether an authorized promotion matches.",
            )
        if deduction.type == "pricing":
            claimed_price = context.get("claimed_unit_price")
            invoice_price = Decimal(str(context["invoice_unit_price"]))
            po_price = Decimal(str(context["po_unit_price"]))
            supported = (
                claimed_price is not None
                and invoice_price != po_price
                and Decimal(str(claimed_price)) == po_price
            )
            return (
                {
                    "claimed_unit_price": claimed_price,
                    "invoice_unit_price": float(invoice_price),
                    "po_unit_price": float(po_price),
                    "evidence_supports_claim": supported,
                },
                "Evaluate only the claimed, invoice, and PO unit prices.",
            )
        claimed_damaged = context.get("claimed_qty")
        pod_damaged = int(context["damaged_qty"])
        supported = (
            claimed_damaged is not None
            and int(claimed_damaged) == pod_damaged
            and pod_damaged > 0
        )
        return (
            {
                "claimed_damaged_qty": claimed_damaged,
                "pod_damaged_qty": pod_damaged,
                "evidence_supports_claim": supported,
            },
            "Use only the claimed and POD damaged quantities.",
        )

    def _prompt(self, deduction: Deduction, context: dict[str, Any]) -> str:
        relevant_context, policy = self._relevant_context(deduction, context)
        evidence = json.dumps(relevant_context, sort_keys=True)
        return f"""You classify retailer deduction claims using supplied internal facts.
Do not invent facts, perform database lookups, or infer hidden ground truth.

Deduction type: {deduction.type}
Claimed amount: {deduction.claimed_amount}
Retailer notes: {deduction.retailer_notes or "(none)"}
Internal facts (authoritative structured context): {evidence}
Decision policy for this deduction type: {policy}

The internal system has already performed the deterministic comparison.
Set is_valid exactly equal to evidence_supports_claim. Do not reverse,
reinterpret, or recalculate that boolean. Your task is to explain it briefly.

Decide whether the retailer's deduction claim is valid. Return only strict JSON:
{{"is_valid": true, "reasoning": "short explanation"}}
Keep reasoning under 40 words.
"""

    def _call_once(self, prompt: str) -> tuple[_OllamaDecision, str]:
        errors: list[str] = []
        for attempt in range(2):
            attempt_prompt = prompt
            if attempt:
                attempt_prompt += (
                    "\nYour prior response was malformed. Return one valid JSON object only."
                )
            try:
                response = self.session.post(
                    f"{self.config.ollama_url}/api/generate",
                    json={
                        "model": self.config.ollama_model,
                        "prompt": attempt_prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.7},
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                raw = response.json().get("response", "")
                parsed = _OllamaDecision.model_validate(_extract_json(raw))
                return parsed, response.text
            except (requests.RequestException, ValueError, ValidationError) as exc:
                errors.append(f"attempt {attempt + 1}: {exc}")
        raise RuntimeError("; ".join(errors))

    def classify(self, deduction: Deduction, context: dict[str, Any]) -> LLMResult:
        prompt = self._prompt(deduction, context)
        decisions: list[_OllamaDecision] = []
        raw_responses: list[str] = []
        errors: list[str] = []

        for vote_number in range(1, 4):
            try:
                decision, raw = self._call_once(prompt)
                decisions.append(decision)
                raw_responses.append(raw)
            except RuntimeError as exc:
                errors.append(f"vote {vote_number}: {exc}")

        if len(decisions) == 3:
            true_count = sum(decision.is_valid for decision in decisions)
            majority = true_count >= 2
            majority_decisions = [
                decision for decision in decisions if decision.is_valid == majority
            ]
            agreement_rate = len(majority_decisions) / 3
            return LLMResult(
                resolved=True,
                is_valid=majority,
                confidence=agreement_rate,
                agreement_rate=agreement_rate,
                votes=[decision.is_valid for decision in decisions],
                reasoning=majority_decisions[0].reasoning,
                raw_responses=raw_responses,
            )

        return LLMResult(
            resolved=False,
            reasoning="Ollama did not return a usable classification; human review required.",
            raw_responses=raw_responses,
            error="; ".join(errors),
        )

    def close(self) -> None:
        self.session.close()
