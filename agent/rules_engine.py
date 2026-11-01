"""Deterministic classification using legitimate internal operational evidence."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import re
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from .config import Settings, settings
from .models import Deduction, RuleResult
from policy import COMPLIANCE_LATE_ALLOWANCE_DAYS


FACTS_QUERY = """
SELECT
    d.claimed_qty,
    d.claimed_unit_price,
    d.claim_date,
    i.invoiced_qty,
    i.unit_price AS invoice_unit_price,
    i.invoice_date,
    po.unit_price AS po_unit_price,
    po.product_sku,
    po.expected_delivery_date,
    pod.delivered_qty,
    pod.damaged_qty,
    pod.delivery_date,
    EXISTS (
        SELECT 1
        FROM trade_promotions tp
        WHERE tp.brand_id = po.brand_id
          AND tp.retailer_id = po.retailer_id
          AND tp.product_sku = po.product_sku
          AND i.invoice_date BETWEEN tp.start_date AND tp.end_date
    ) AS matching_promo
FROM deductions d
JOIN invoices i ON i.id = d.invoice_id
JOIN purchase_orders po ON po.id = i.purchase_order_id
JOIN proof_of_delivery pod ON pod.purchase_order_id = po.id
WHERE d.id = %s AND i.id = %s
"""


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


TYPE_PATTERNS = {
    "shortage": re.compile(r"\b(shortage|short|shrt|qty)\b", re.IGNORECASE),
    "promotional": re.compile(
        r"\b(promo(?:tional)?|allowance|alowance)\b", re.IGNORECASE
    ),
    "pricing": re.compile(r"\b(pricing|price|prce|unit cost)\b", re.IGNORECASE),
    "compliance": re.compile(r"\b(compliance|compl|late fee)\b", re.IGNORECASE),
    "damage": re.compile(r"\b(damage(?:d)?|damaged|dmged)\b", re.IGNORECASE),
}
QUANTITY_PATTERN = re.compile(
    r"\b(?:qty|quantity|short(?:age)?|shrt|damage(?:d)?|dmged)\b"
    r"[^\d$]{0,16}(\d{1,3})\b",
    re.IGNORECASE,
)
AMOUNT_PATTERN = re.compile(
    r"(?:\$\s*|\b(?:amount|amt|deduction)\s*[:=]?\s*)(\d+(?:\.\d{1,2})?)\b",
    re.IGNORECASE,
)


def parse_retailer_notes(notes: str) -> dict[str, Any]:
    """Extract claim hints while avoiding PO/invoice numbers as quantities."""
    detected_types = [
        deduction_type
        for deduction_type, pattern in TYPE_PATTERNS.items()
        if pattern.search(notes)
    ]
    quantity_match = QUANTITY_PATTERN.search(notes)
    amount_match = AMOUNT_PATTERN.search(notes)
    is_clean_prefix = bool(re.match(r"^\s*reason\s*:", notes, re.IGNORECASE))
    is_terse_structured = "/" in notes and len(notes.split()) <= 12
    has_explicit_value = quantity_match is not None or amount_match is not None
    return {
        "detected_types": detected_types,
        "quantity": int(quantity_match.group(1)) if quantity_match else None,
        "amount": float(amount_match.group(1)) if amount_match else None,
        "is_clean_prefix": is_clean_prefix,
        "is_terse_structured": is_terse_structured,
        "has_explicit_value": has_explicit_value,
    }


class RulesEngine:
    def __init__(self, config: Settings = settings) -> None:
        self.connection = psycopg2.connect(config.database_url)

    def _facts(self, deduction: Deduction) -> dict[str, Any]:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(FACTS_QUERY, (deduction.id, deduction.invoice_id))
            row = cursor.fetchone()
        if row is None:
            raise LookupError(f"No internal evidence found for deduction {deduction.id}")
        return {key: _json_value(value) for key, value in row.items()}

    def evaluate(self, deduction: Deduction) -> RuleResult:
        facts = self._facts(deduction)
        notes = (deduction.retailer_notes or "").strip()
        parsed = parse_retailer_notes(notes)
        facts["parsed_notes"] = parsed
        matching_type = deduction.type in parsed["detected_types"]
        parseable_claim = matching_type and (
            parsed["is_clean_prefix"]
            or parsed["is_terse_structured"]
            or parsed["has_explicit_value"]
        )

        if not parseable_claim:
            if not parsed["detected_types"]:
                detail = "no known deduction-type keyword was found"
            elif not matching_type:
                detail = "note keywords do not match the deduction type"
            else:
                detail = "type was found, but prose contains no quantity, amount, or structured separators"
            return RuleResult(
                resolved=False,
                reasoning=f"Retailer notes remain ambiguous: {detail}.",
                context=facts,
            )

        if deduction.type == "shortage":
            invoiced = int(facts["invoiced_qty"])
            delivered = int(facts["delivered_qty"])
            claimed = parsed["quantity"] or facts["claimed_qty"]
            actual_short = max(0, invoiced - delivered)
            facts["actual_short_qty"] = actual_short
            if actual_short == 0:
                return RuleResult(
                    resolved=True,
                    is_valid=False,
                    confidence=0.99,
                    reasoning=f"POD shows all {invoiced} invoiced units were delivered; no shortage occurred.",
                    context=facts,
                )
            matches = claimed is not None and int(claimed) == actual_short
            return RuleResult(
                resolved=True,
                is_valid=matches,
                confidence=0.98,
                reasoning=(
                    f"POD confirms the claimed shortage of {actual_short} units."
                    if matches
                    else f"POD supports {actual_short} short units, not the claimed {claimed}."
                ),
                context=facts,
            )

        if deduction.type == "promotional":
            matched = bool(facts["matching_promo"])
            return RuleResult(
                resolved=True,
                is_valid=matched,
                confidence=0.98,
                reasoning=(
                    "An authorized promotion matches the retailer, product, and invoice date."
                    if matched
                    else "No authorized promotion matches the retailer, product, and invoice date."
                ),
                context=facts,
            )

        if deduction.type == "pricing":
            invoice_price = Decimal(str(facts["invoice_unit_price"]))
            po_price = Decimal(str(facts["po_unit_price"]))
            claimed_price = facts["claimed_unit_price"]
            valid = invoice_price != po_price and (
                claimed_price is None or Decimal(str(claimed_price)) == po_price
            )
            return RuleResult(
                resolved=True,
                is_valid=valid,
                confidence=0.97,
                reasoning=(
                    f"Invoice unit price {invoice_price} differs from PO price {po_price}."
                    if valid
                    else f"Invoice price {invoice_price}, PO price {po_price}, and claimed price {claimed_price} do not support the claim."
                ),
                context=facts,
            )

        if deduction.type == "damage":
            damaged = int(facts["damaged_qty"])
            claimed = facts["claimed_qty"]
            valid = damaged > 0 and claimed is not None and int(claimed) == damaged
            return RuleResult(
                resolved=True,
                is_valid=valid,
                confidence=0.97,
                reasoning=(
                    f"POD records the claimed {damaged} damaged units."
                    if valid
                    else f"POD records {damaged} damaged units versus {claimed} claimed."
                ),
                context=facts,
            )

        if deduction.type == "compliance":
            delivered = date.fromisoformat(str(facts["delivery_date"]))
            expected = date.fromisoformat(str(facts["expected_delivery_date"]))
            days_late = (delivered - expected).days
            facts["days_late"] = days_late
            valid = days_late > COMPLIANCE_LATE_ALLOWANCE_DAYS
            return RuleResult(
                resolved=True,
                is_valid=valid,
                confidence=0.95,
                reasoning=(
                    f"Delivery was {days_late} days late, beyond the {COMPLIANCE_LATE_ALLOWANCE_DAYS}-day allowance."
                    if valid
                    else f"Delivery timing ({days_late} days late) is within the {COMPLIANCE_LATE_ALLOWANCE_DAYS}-day allowance."
                ),
                context=facts,
            )

        return RuleResult(
            resolved=False,
            reasoning=f"No deterministic rule is available for {deduction.type}.",
            context=facts,
        )

    def close(self) -> None:
        self.connection.close()
