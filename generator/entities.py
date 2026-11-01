"""Generate the business entities and evidence used by deductions."""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from .config import PRODUCTS, fake


def generate_brands(count: int | None = None) -> list[dict]:
    count = count or random.randint(1, 2)
    candidates = ["Northstar Pantry Co.", "Juniper Consumer Brands"]
    return [{"name": name} for name in candidates[:count]]


def generate_retailers() -> list[dict]:
    return [
        {"name": "Walmart", "retailer_code": "WMT"},
        {"name": "Target", "retailer_code": "TGT"},
        {"name": "Costco", "retailer_code": "COST"},
        {"name": "Kroger", "retailer_code": "KRO"},
    ]


def generate_purchase_orders(
    brand_ids: list[int], retailer_ids: list[int], count: int = 420
) -> list[dict]:
    today = date.today()
    orders = []
    for i in range(1, count + 1):
        product = random.choice(PRODUCTS)
        order_date = today - timedelta(days=random.randint(40, 360))
        orders.append(
            {
                "po_number": f"PO-{order_date:%y%m}-{i:06d}",
                "brand_id": random.choice(brand_ids),
                "retailer_id": random.choice(retailer_ids),
                "product_sku": product["sku"],
                "product_name": product["name"],
                "order_date": order_date,
                "expected_delivery_date": order_date + timedelta(days=random.randint(5, 14)),
                "ordered_qty": random.choice([48, 72, 96, 120, 144, 192, 240, 288]),
                "unit_price": Decimal(str(product["unit_price"])),
            }
        )
    return orders


def generate_invoices(purchase_orders: list[dict]) -> list[dict]:
    invoices = []
    for i, po in enumerate(purchase_orders, 1):
        qty = po["ordered_qty"]
        # A small number of source invoices contain a real pricing variance.
        variance = Decimal(random.choice(["0", "0", "0", "0", "0.15", "-0.10"]))
        unit_price = max(Decimal("0.01"), po["unit_price"] + variance)
        invoices.append(
            {
                "invoice_number": f"INV-{i:07d}",
                "purchase_order_id": po["id"],
                "invoice_date": po["expected_delivery_date"] - timedelta(days=1),
                "invoiced_qty": qty,
                "unit_price": unit_price,
                "gross_amount": (unit_price * qty).quantize(Decimal("0.01")),
            }
        )
    return invoices


def generate_proof_of_delivery(purchase_orders: list[dict]) -> list[dict]:
    pods = []
    for i, po in enumerate(purchase_orders, 1):
        actual_short = random.choices([0, random.randint(1, 12)], weights=[0.78, 0.22])[0]
        damaged = random.choices([0, random.randint(1, 6)], weights=[0.86, 0.14])[0]
        delivered = max(0, po["ordered_qty"] - actual_short)
        pods.append(
            {
                "purchase_order_id": po["id"],
                "delivery_date": po["expected_delivery_date"] + timedelta(days=random.randint(-1, 3)),
                "delivered_qty": delivered,
                "damaged_qty": min(damaged, delivered),
                "signed_by": fake.name(),
                "pod_reference": f"POD-{i:07d}",
            }
        )
    return pods


def generate_trade_promotions(
    brand_ids: list[int], retailer_ids: list[int], count: int = 180
) -> list[dict]:
    today = date.today()
    promotions = []
    for i in range(1, count + 1):
        product = random.choice(PRODUCTS)
        start = today - timedelta(days=random.randint(30, 390))
        duration = random.choice([7, 14, 21, 28])
        discount = random.choice([5, 10, 12.5, 15, 20, 25])
        promotions.append(
            {
                "brand_id": random.choice(brand_ids),
                "retailer_id": random.choice(retailer_ids),
                "product_sku": product["sku"],
                "promotion_name": f"{fake.word().title()} {product['name']} Event {i}",
                "start_date": start,
                "end_date": start + timedelta(days=duration - 1),
                "discount_percent": Decimal(str(discount)),
            }
        )
    return promotions


def generate_remittances(invoices: list[dict]) -> list[dict]:
    return [
        {
            "remittance_number": f"REM-{i:07d}",
            "invoice_id": invoice["id"],
            "remittance_date": invoice["invoice_date"] + timedelta(days=random.randint(25, 55)),
            "invoice_amount": invoice["gross_amount"],
            "paid_amount": invoice["gross_amount"],
        }
        for i, invoice in enumerate(invoices, 1)
    ]
