"""Generate deductions whose labels can be proven from source evidence."""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from .config import DEDUCTION_TYPE_WEIGHTS
from policy import COMPLIANCE_LATE_ALLOWANCE_DAYS


def _note(style: str, deduction_type: str, po_number: str) -> str:
    reason = deduction_type.upper()
    if style == "structured":
        details = {
            "shortage": "PO# mismatch on qty",
            "promotional": "allowance not reflected",
            "pricing": "unit cost variance",
            "compliance": "delivery requirement missed",
            "damage": "cases received damaged",
        }
        return f"Reason: {reason}. PO# {po_number}. {details[deduction_type]}."
    if style == "email":
        return (
            f"Hi team, we took a {deduction_type} deduction on {po_number}. "
            "Can you review and clear this against the remittance? Thanks."
        )
    snippets = {
        "shortage": "qty shrt",
        "promotional": "promo alowance",
        "pricing": "prce diff",
        "compliance": "compl fee",
        "damage": "dmged cses",
    }
    return f"{snippets[deduction_type]} / {po_number[-6:]} / chk docs"


def _matching_promotion(promotions: list[dict], po: dict, invoice_date) -> dict | None:
    matches = [
        promo
        for promo in promotions
        if promo["brand_id"] == po["brand_id"]
        and promo["retailer_id"] == po["retailer_id"]
        and promo["product_sku"] == po["product_sku"]
        and promo["start_date"] <= invoice_date <= promo["end_date"]
    ]
    return random.choice(matches) if matches else None


def generate_deductions(
    invoices: list[dict],
    purchase_orders: list[dict],
    pods: list[dict],
    promotions: list[dict],
    remittances: list[dict],
    count: int,
) -> tuple[list[dict], list[dict]]:
    po_by_id = {po["id"]: po for po in purchase_orders}
    pod_by_po = {pod["purchase_order_id"]: pod for pod in pods}
    remittance_by_invoice = {rem["invoice_id"]: rem for rem in remittances}
    types, weights = zip(*DEDUCTION_TYPE_WEIGHTS.items())
    deductions, truths = [], []

    # Fixed label allocation prevents normal random variation from missing the target.
    desired_validity = [True] * round(count * 0.40)
    desired_validity.extend([False] * (count - len(desired_validity)))
    random.shuffle(desired_validity)

    for i, wanted_valid in enumerate(desired_validity, 1):
        deduction_type = random.choices(types, weights=weights, k=1)[0]
        candidates = invoices

        # Pick evidence capable of producing the requested class where practical.
        if deduction_type == "shortage" and wanted_valid:
            supported = [
                inv for inv in invoices
                if pod_by_po[inv["purchase_order_id"]]["delivered_qty"] < inv["invoiced_qty"]
            ]
            candidates = supported or invoices
        elif deduction_type == "damage" and wanted_valid:
            supported = [
                inv for inv in invoices
                if pod_by_po[inv["purchase_order_id"]]["damaged_qty"] > 0
            ]
            candidates = supported or invoices
        elif deduction_type == "pricing" and wanted_valid:
            supported = [
                inv for inv in invoices
                if inv["unit_price"] != po_by_id[inv["purchase_order_id"]]["unit_price"]
            ]
            candidates = supported or invoices
        elif deduction_type == "promotional":
            matched = [
                inv for inv in invoices
                if _matching_promotion(promotions, po_by_id[inv["purchase_order_id"]], inv["invoice_date"])
            ]
            unmatched = [inv for inv in invoices if inv not in matched]
            candidates = (matched if wanted_valid else unmatched) or invoices
        elif deduction_type == "compliance" and wanted_valid:
            supported = [
                inv for inv in invoices
                if (
                    pod_by_po[inv["purchase_order_id"]]["delivery_date"]
                    - po_by_id[inv["purchase_order_id"]]["expected_delivery_date"]
                ).days
                > COMPLIANCE_LATE_ALLOWANCE_DAYS
            ]
            candidates = supported or invoices

        invoice = random.choice(candidates)
        po = po_by_id[invoice["purchase_order_id"]]
        pod = pod_by_po[po["id"]]
        remittance = remittance_by_invoice[invoice["id"]]
        claim_date = remittance["remittance_date"]
        claimed_qty = None
        claimed_unit_price = None

        if deduction_type == "shortage":
            actual_short = invoice["invoiced_qty"] - pod["delivered_qty"]
            claimed_qty = actual_short if wanted_valid and actual_short > 0 else max(1, actual_short + random.randint(1, 8))
            is_valid = actual_short > 0 and claimed_qty == actual_short
            amount = Decimal(claimed_qty) * invoice["unit_price"]
            reason = (
                f"POD confirms {claimed_qty} units short."
                if is_valid else f"POD supports {actual_short} short, not the claimed {claimed_qty}."
            )
        elif deduction_type == "pricing":
            contract_price = po["unit_price"]
            if wanted_valid and invoice["unit_price"] != contract_price:
                claimed_unit_price = contract_price
            else:
                claimed_unit_price = max(Decimal("0.01"), contract_price - Decimal(random.choice(["0.10", "0.25", "0.40"])))
                if claimed_unit_price == invoice["unit_price"]:
                    claimed_unit_price -= Decimal("0.05")
            is_valid = invoice["unit_price"] != contract_price and claimed_unit_price == contract_price
            amount = abs(invoice["unit_price"] - claimed_unit_price) * invoice["invoiced_qty"]
            reason = (
                f"Invoice price {invoice['unit_price']} differs from PO price {contract_price}."
                if is_valid else f"PO price {contract_price} does not support claimed price {claimed_unit_price}."
            )
        elif deduction_type == "promotional":
            promo = _matching_promotion(promotions, po, invoice["invoice_date"])
            is_valid = promo is not None
            if promo:
                amount = invoice["gross_amount"] * promo["discount_percent"] / Decimal("100")
                reason = f"Authorized promotion {promo['promotion_name']} covers invoice date and SKU."
            else:
                amount = invoice["gross_amount"] * Decimal(random.choice(["0.05", "0.10", "0.15"]))
                reason = "No authorized promotion matches retailer, SKU, and invoice date."
        elif deduction_type == "damage":
            claimed_qty = pod["damaged_qty"] if wanted_valid and pod["damaged_qty"] > 0 else pod["damaged_qty"] + random.randint(1, 5)
            is_valid = pod["damaged_qty"] > 0 and claimed_qty == pod["damaged_qty"]
            amount = Decimal(claimed_qty) * invoice["unit_price"]
            reason = (
                f"POD records {claimed_qty} damaged units."
                if is_valid else f"POD records {pod['damaged_qty']} damaged, not {claimed_qty}."
            )
        else:  # compliance: evidence is the delivery date versus the PO window.
            days_late = (pod["delivery_date"] - po["expected_delivery_date"]).days
            is_valid = days_late > COMPLIANCE_LATE_ALLOWANCE_DAYS
            amount = invoice["gross_amount"] * Decimal("0.02")
            reason = (
                f"Delivery was {days_late} days late, exceeding {COMPLIANCE_LATE_ALLOWANCE_DAYS}-day allowance."
                if is_valid
                else f"Delivery timing ({days_late} days) is within the {COMPLIANCE_LATE_ALLOWANCE_DAYS}-day allowance."
            )

        amount = max(Decimal("0.01"), amount.quantize(Decimal("0.01")))
        deductions.append(
            {
                "deduction_number": f"DED-{i:07d}",
                "invoice_id": invoice["id"],
                "remittance_id": remittance["id"],
                "type": deduction_type,
                "status": "pending",
                "claim_date": claim_date + timedelta(days=random.randint(0, 5)),
                "claimed_qty": claimed_qty,
                "claimed_unit_price": claimed_unit_price,
                "amount": amount,
                "retailer_notes": _note(
                    random.choice(["structured", "email", "sparse"]),
                    deduction_type,
                    po["po_number"],
                ),
            }
        )
        truths.append({"is_valid": is_valid, "true_reason": reason})

    return deductions, truths
