"""Spot-check 8 randomly selected Groq-processed cases with underlying database facts."""

from __future__ import annotations

import json
import random
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("postgresql://localhost:5432/deductiondesk")

with conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute(
        """
        SELECT d.id, d.type, d.amount, d.claimed_qty, d.claimed_unit_price, d.retailer_notes,
               i.invoice_number, i.invoiced_qty, i.unit_price AS invoice_unit_price, i.invoice_date,
               po.po_number, po.unit_price AS po_unit_price, po.expected_delivery_date, po.product_sku,
               pod.delivered_qty, pod.damaged_qty, pod.delivery_date,
               EXISTS (
                   SELECT 1 FROM trade_promotions tp
                   WHERE tp.brand_id = po.brand_id AND tp.retailer_id = po.retailer_id
                     AND tp.product_sku = po.product_sku
                     AND i.invoice_date BETWEEN tp.start_date AND tp.end_date
               ) AS matching_promo,
               ad.is_valid AS final_decision, ad.confidence, ad.reasoning AS final_reasoning,
               gt.is_valid AS gt_is_valid, gt.true_reason AS gt_reason
        FROM agent_decisions ad
        JOIN deductions d ON d.id = ad.deduction_id
        JOIN invoices i ON i.id = d.invoice_id
        JOIN purchase_orders po ON po.id = i.purchase_order_id
        JOIN proof_of_delivery pod ON pod.purchase_order_id = po.id
        JOIN ground_truth gt ON gt.deduction_id = d.id
        WHERE ad.method = 'llm' AND ad.created_at > '2026-11-05'
        ORDER BY d.id
        """
    )
    all_cases = cur.fetchall()

by_type = {}
for c in all_cases:
    by_type.setdefault(c["type"], []).append(c)

random.seed(12345)
sample = []
# Pick 2 shortage, 2 promotional, 2 compliance, 1 pricing, 1 damage = 8 cases
sample.extend(random.sample(by_type["shortage"], 2))
sample.extend(random.sample(by_type["promotional"], 2))
sample.extend(random.sample(by_type["compliance"], 2))
sample.extend(random.sample(by_type["pricing"], 1))
sample.extend(random.sample(by_type["damage"], 1))

for idx, s in enumerate(sample, 1):
    print("=" * 80)
    print(f"CASE {idx}: Deduction #{s['id']} ({s['type'].upper()})")
    print("=" * 80)
    print("1. UNDERLYING SOURCE DATA (FROM DB):")
    print(f"   Retailer Notes:    {s['retailer_notes']}")
    print(f"   Claimed Amount:    ${s['amount']}")
    print(f"   Claimed Qty:       {s['claimed_qty']} | Claimed Unit Price: {s['claimed_unit_price']}")
    print(f"   Invoice:           {s['invoice_number']} | Invoiced Qty: {s['invoiced_qty']} | Price: ${s['invoice_unit_price']} | Date: {s['invoice_date']}")
    print(f"   PO:                {s['po_number']} | PO Price: ${s['po_unit_price']} | Expected Delivery: {s['expected_delivery_date']} | SKU: {s['product_sku']}")
    print(f"   POD:               Delivered: {s['delivered_qty']} | Damaged: {s['damaged_qty']} | Actual Delivery: {s['delivery_date']}")
    print(f"   Matching Promo:    {s['matching_promo']}")
    if s["type"] == "compliance":
        days_late = (s["delivery_date"] - s["expected_delivery_date"]).days
        print(f"   Timing Calc:       {s['delivery_date']} - {s['expected_delivery_date']} = {days_late} days late (allowance is 1 day)")
    if s["type"] == "shortage":
        actual_short = max(0, s["invoiced_qty"] - s["delivered_qty"])
        print(f"   Shortage Calc:     max(0, {s['invoiced_qty']} - {s['delivered_qty']}) = {actual_short} units actual short")
    print(f"   Ground Truth:      is_valid={s['gt_is_valid']} | Reason: {s['gt_reason']}")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT call_number, is_valid, reasoning
            FROM agent_llm_calls
            WHERE deduction_id = %s
            ORDER BY call_number
            """,
            (s["id"],),
        )
        calls = cur.fetchall()

    print("\n2. FULL REASONING TEXT FROM ALL 3 VOTES:")
    for c in calls:
        print(f"   [Vote {c['call_number']}] (is_valid={c['is_valid']})")
        print(f"       \"{c['reasoning']}\"")
    print(f"   Final Decision:    is_valid={s['final_decision']} (confidence: {s['confidence']:.2f})")
    print()

conn.close()

