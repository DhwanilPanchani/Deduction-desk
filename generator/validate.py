"""Validate a populated DeductionDesk database and print a summary."""

from __future__ import annotations

import sys

import psycopg2

from .config import DATABASE_URL

TABLES = [
    "brands",
    "retailers",
    "purchase_orders",
    "invoices",
    "proof_of_delivery",
    "trade_promotions",
    "remittances",
    "deductions",
    "ground_truth",
    "disputes",
]

ORPHAN_CHECKS = {
    "purchase_orders.brand": "SELECT COUNT(*) FROM purchase_orders c LEFT JOIN brands p ON p.id=c.brand_id WHERE p.id IS NULL",
    "purchase_orders.retailer": "SELECT COUNT(*) FROM purchase_orders c LEFT JOIN retailers p ON p.id=c.retailer_id WHERE p.id IS NULL",
    "invoices.purchase_order": "SELECT COUNT(*) FROM invoices c LEFT JOIN purchase_orders p ON p.id=c.purchase_order_id WHERE p.id IS NULL",
    "pod.purchase_order": "SELECT COUNT(*) FROM proof_of_delivery c LEFT JOIN purchase_orders p ON p.id=c.purchase_order_id WHERE p.id IS NULL",
    "promotions.brand": "SELECT COUNT(*) FROM trade_promotions c LEFT JOIN brands p ON p.id=c.brand_id WHERE p.id IS NULL",
    "promotions.retailer": "SELECT COUNT(*) FROM trade_promotions c LEFT JOIN retailers p ON p.id=c.retailer_id WHERE p.id IS NULL",
    "remittances.invoice": "SELECT COUNT(*) FROM remittances c LEFT JOIN invoices p ON p.id=c.invoice_id WHERE p.id IS NULL",
    "deductions.invoice": "SELECT COUNT(*) FROM deductions c LEFT JOIN invoices p ON p.id=c.invoice_id WHERE p.id IS NULL",
    "deductions.remittance": "SELECT COUNT(*) FROM deductions c LEFT JOIN remittances p ON p.id=c.remittance_id WHERE p.id IS NULL",
    "ground_truth.deduction": "SELECT COUNT(*) FROM ground_truth c LEFT JOIN deductions p ON p.id=c.deduction_id WHERE p.id IS NULL",
    "disputes.deduction": "SELECT COUNT(*) FROM disputes c LEFT JOIN deductions p ON p.id=c.deduction_id WHERE p.id IS NULL",
}


def validate() -> bool:
    failures = []
    with psycopg2.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        print("DeductionDesk validation report")
        print("=" * 32)
        print("Row counts:")
        counts = {}
        for table in TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]
            print(f"  {table:<20} {counts[table]:>5}")

        cursor.execute(
            "SELECT is_valid, COUNT(*) FROM ground_truth GROUP BY is_valid ORDER BY is_valid DESC"
        )
        balance = dict(cursor.fetchall())
        total = sum(balance.values())
        valid = balance.get(True, 0)
        invalid = balance.get(False, 0)
        print("\nGround-truth class balance:")
        print(f"  valid (retailer claim supported)  {valid:>5} ({valid / total:.1%})")
        print(f"  invalid / recoverable            {invalid:>5} ({invalid / total:.1%})")

        print("\nForeign-key orphan checks:")
        for name, query in ORPHAN_CHECKS.items():
            cursor.execute(query)
            orphan_count = cursor.fetchone()[0]
            print(f"  {name:<28} {orphan_count}")
            if orphan_count:
                failures.append(f"{name}: {orphan_count} orphan(s)")

        if not 500 <= counts["deductions"] <= 1000:
            failures.append("deduction count is outside 500-1000")
        if counts["ground_truth"] != counts["deductions"]:
            failures.append("not every deduction has exactly one ground-truth row")
        if total and not 0.55 <= invalid / total <= 0.65:
            failures.append("recoverable/invalid share is outside 55%-65%")

    print("\nResult:", "FAIL" if failures else "PASS")
    for failure in failures:
        print(f"  - {failure}")
    return not failures


if __name__ == "__main__":
    sys.exit(0 if validate() else 1)
