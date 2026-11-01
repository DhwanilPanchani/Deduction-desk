"""Recreate and populate the DeductionDesk PostgreSQL database."""

from __future__ import annotations

from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from .config import DATABASE_URL, DEDUCTION_COUNT
from .deductions import generate_deductions
from .entities import (
    generate_brands,
    generate_invoices,
    generate_proof_of_delivery,
    generate_purchase_orders,
    generate_remittances,
    generate_retailers,
    generate_trade_promotions,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def insert_rows(cursor, table: str, rows: list[dict], returning_ids: bool = True) -> list[dict]:
    if not rows:
        return rows
    columns = list(rows[0])
    values = [[row[column] for column in columns] for row in rows]
    returning = " RETURNING id" if returning_ids else ""
    query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s{returning}"
    inserted = execute_values(cursor, query, values, fetch=returning_ids)
    if returning_ids:
        for row, (row_id,) in zip(rows, inserted):
            row["id"] = row_id
    return rows


def seed() -> None:
    with psycopg2.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA_PATH.read_text())

            brands = insert_rows(cursor, "brands", generate_brands())
            retailers = insert_rows(cursor, "retailers", generate_retailers())
            brand_ids = [row["id"] for row in brands]
            retailer_ids = [row["id"] for row in retailers]

            purchase_orders = insert_rows(
                cursor, "purchase_orders", generate_purchase_orders(brand_ids, retailer_ids)
            )
            invoices = insert_rows(cursor, "invoices", generate_invoices(purchase_orders))
            pods = insert_rows(cursor, "proof_of_delivery", generate_proof_of_delivery(purchase_orders))
            promotions = insert_rows(
                cursor, "trade_promotions", generate_trade_promotions(brand_ids, retailer_ids)
            )
            remittances = insert_rows(cursor, "remittances", generate_remittances(invoices))
            deductions, truths = generate_deductions(
                invoices, purchase_orders, pods, promotions, remittances, DEDUCTION_COUNT
            )
            deductions = insert_rows(cursor, "deductions", deductions)
            for truth, deduction in zip(truths, deductions):
                truth["deduction_id"] = deduction["id"]
            insert_rows(cursor, "ground_truth", truths)

    print(
        f"Seeded DeductionDesk: {len(brands)} brands, {len(retailers)} retailers, "
        f"{len(invoices)} invoices, and {len(deductions)} deductions."
    )


if __name__ == "__main__":
    seed()
