"""Build evidence-backed markdown packets for confident invalid deductions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from psycopg2.extras import RealDictCursor

from .config import Settings, settings

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

ELIGIBLE_QUERY = """
SELECT
    d.id AS deduction_id,
    d.deduction_number,
    d.type AS deduction_type,
    d.amount AS claimed_amount,
    d.claimed_qty,
    d.claimed_unit_price,
    d.claim_date,
    ad.confidence,
    ad.reasoning,
    ad.method,
    r.name AS retailer,
    i.invoice_number,
    i.invoice_date,
    i.invoiced_qty,
    i.unit_price AS invoice_unit_price,
    po.po_number,
    po.product_sku,
    po.product_name,
    po.unit_price AS po_unit_price,
    po.expected_delivery_date,
    pod.delivered_qty,
    pod.damaged_qty,
    pod.delivery_date,
    promo.promotion_name,
    promo.discount_percent,
    promo.start_date AS promotion_start_date,
    promo.end_date AS promotion_end_date
FROM agent_decisions ad
JOIN deductions d ON d.id = ad.deduction_id
JOIN invoices i ON i.id = d.invoice_id
JOIN purchase_orders po ON po.id = i.purchase_order_id
JOIN retailers r ON r.id = po.retailer_id
JOIN proof_of_delivery pod ON pod.purchase_order_id = po.id
LEFT JOIN LATERAL (
    SELECT tp.promotion_name, tp.discount_percent, tp.start_date, tp.end_date
    FROM trade_promotions tp
    WHERE tp.brand_id = po.brand_id
      AND tp.retailer_id = po.retailer_id
      AND tp.product_sku = po.product_sku
      AND i.invoice_date BETWEEN tp.start_date AND tp.end_date
    ORDER BY tp.start_date DESC
    LIMIT 1
) promo ON TRUE
LEFT JOIN disputes existing ON existing.deduction_id = d.id
WHERE ad.is_valid = FALSE
  AND ad.needs_human_review = FALSE
  AND existing.id IS NULL
ORDER BY d.id
"""


@dataclass(frozen=True)
class DisputePacket:
    deduction_id: int
    claimed_amount: Decimal
    agent_confidence: float
    markdown: str


@dataclass(frozen=True)
class PacketBatch:
    packets: list[DisputePacket]
    skipped_flagged: int
    skipped_already_filed: int


def _display(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _evidence(row: dict[str, Any]) -> list[str]:
    deduction_type = row["deduction_type"]
    common = [
        f"Invoice {row['invoice_number']} was issued for {row['invoiced_qty']} units at ${Decimal(row['invoice_unit_price']):.2f} per unit.",
        f"Proof of delivery {row['delivery_date'].isoformat()} records {row['delivered_qty']} units delivered and {row['damaged_qty']} damaged units.",
    ]

    if deduction_type == "shortage":
        actual_short = max(0, row["invoiced_qty"] - row["delivered_qty"])
        return common + [
            f"The operational records support an actual shortage of {actual_short} units; the retailer claimed {row['claimed_qty']} units.",
            f"POD delivered quantity ({row['delivered_qty']}) was compared directly with invoiced quantity ({row['invoiced_qty']}).",
        ]
    if deduction_type == "promotional":
        if row["promotion_name"]:
            promo = (
                f"Authorized promotion '{row['promotion_name']}' ran from "
                f"{row['promotion_start_date']} through {row['promotion_end_date']} "
                f"at {row['discount_percent']}%."
            )
        else:
            promo = (
                f"No authorized promotion matches retailer {row['retailer']}, SKU "
                f"{row['product_sku']}, and invoice date {row['invoice_date']}."
            )
        return common + [promo]
    if deduction_type == "pricing":
        return common + [
            f"PO unit price was ${Decimal(row['po_unit_price']):.2f}; invoice unit price was ${Decimal(row['invoice_unit_price']):.2f}.",
            f"The retailer's claimed unit price was {_display(row['claimed_unit_price'])}.",
        ]
    if deduction_type == "damage":
        return common + [
            f"The retailer claimed {row['claimed_qty']} damaged units, while the signed POD records {row['damaged_qty']}.",
        ]
    if deduction_type == "compliance":
        days_late = (row["delivery_date"] - row["expected_delivery_date"]).days
        return common + [
            f"Expected delivery date was {row['expected_delivery_date']}; actual delivery date was {row['delivery_date']} ({days_late} days difference).",
        ]
    return common


class DisputeBuilder:
    def __init__(self, config: Settings = settings) -> None:
        self.connection = psycopg2.connect(config.database_url)
        environment = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=False,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.template = environment.get_template("dispute_packet.md.j2")

    def build(self) -> PacketBatch:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(ELIGIBLE_QUERY)
            rows = cursor.fetchall()
            cursor.execute(
                "SELECT COUNT(*) FROM agent_decisions WHERE is_valid=FALSE AND needs_human_review=TRUE"
            )
            skipped_flagged = cursor.fetchone()["count"]
            cursor.execute(
                """SELECT COUNT(*) FROM agent_decisions ad
                   JOIN disputes dp ON dp.deduction_id=ad.deduction_id
                   WHERE ad.is_valid=FALSE AND ad.needs_human_review=FALSE"""
            )
            skipped_already_filed = cursor.fetchone()["count"]

        packets = []
        for row in rows:
            context = dict(row)
            context.update(
                claimed_amount=float(row["claimed_amount"]),
                confidence=float(row["confidence"]),
                evidence=_evidence(row),
            )
            markdown = self.template.render(**context).strip() + "\n"
            packets.append(
                DisputePacket(
                    deduction_id=row["deduction_id"],
                    claimed_amount=row["claimed_amount"],
                    agent_confidence=float(row["confidence"]),
                    markdown=markdown,
                )
            )
        return PacketBatch(packets, skipped_flagged, skipped_already_filed)

    def close(self) -> None:
        self.connection.close()
