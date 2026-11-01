"""Hand-constructed unit tests for deterministic deduction rules."""

from decimal import Decimal

from agent.models import Deduction
from agent.rules_engine import RulesEngine


def deduction(deduction_type: str, notes: str) -> Deduction:
    return Deduction(
        id=1,
        retailer="Test Retailer",
        type=deduction_type,
        claimed_amount=Decimal("10.00"),
        status="pending",
        retailer_notes=notes,
        invoice_id=1,
    )


def evaluate(deduction_type: str, notes: str, **overrides: object):
    facts: dict[str, object] = {
        "claimed_qty": None,
        "claimed_unit_price": None,
        "claim_date": "2026-01-10",
        "invoiced_qty": 100,
        "invoice_unit_price": 5.0,
        "invoice_date": "2026-01-08",
        "po_unit_price": 5.0,
        "product_sku": "TEST-SKU",
        "expected_delivery_date": "2026-01-10",
        "delivered_qty": 100,
        "damaged_qty": 0,
        "delivery_date": "2026-01-10",
        "matching_promo": False,
    }
    facts.update(overrides)
    engine = RulesEngine.__new__(RulesEngine)
    engine._facts = lambda _deduction: facts.copy()  # type: ignore[method-assign]
    return engine.evaluate(deduction(deduction_type, notes))


def test_shortage_exact_match_is_valid() -> None:
    result = evaluate(
        "shortage",
        "Reason: SHORTAGE. qty 5.",
        claimed_qty=5,
        invoiced_qty=100,
        delivered_qty=95,
    )
    assert result.resolved is True
    assert result.is_valid is True
    assert result.confidence == 0.98


def test_shortage_quantity_mismatch_is_invalid() -> None:
    result = evaluate(
        "shortage",
        "Reason: SHORTAGE. qty 7.",
        claimed_qty=7,
        invoiced_qty=100,
        delivered_qty=95,
    )
    assert result.resolved is True
    assert result.is_valid is False


def test_shortage_zero_actual_quantity_is_invalid() -> None:
    result = evaluate(
        "shortage",
        "Reason: SHORTAGE. qty 0.",
        claimed_qty=0,
        invoiced_qty=100,
        delivered_qty=100,
    )
    assert result.resolved is True
    assert result.is_valid is False
    assert result.confidence == 0.99


def test_promotional_authorization_match_is_valid() -> None:
    result = evaluate(
        "promotional",
        "Reason: PROMOTIONAL. allowance applied.",
        matching_promo=True,
    )
    assert result.resolved is True
    assert result.is_valid is True


def test_promotional_no_authorization_is_invalid() -> None:
    result = evaluate(
        "promotional",
        "Reason: PROMOTIONAL. allowance applied.",
        matching_promo=False,
    )
    assert result.resolved is True
    assert result.is_valid is False


def test_compliance_exact_one_day_boundary_is_invalid() -> None:
    result = evaluate(
        "compliance",
        "Reason: COMPLIANCE. late fee.",
        expected_delivery_date="2026-01-10",
        delivery_date="2026-01-11",
    )
    assert result.resolved is True
    assert result.is_valid is False


def test_compliance_two_days_late_is_valid() -> None:
    result = evaluate(
        "compliance",
        "Reason: COMPLIANCE. late fee.",
        expected_delivery_date="2026-01-10",
        delivery_date="2026-01-12",
    )
    assert result.resolved is True
    assert result.is_valid is True


def test_pricing_without_invoice_po_variance_is_invalid() -> None:
    result = evaluate(
        "pricing",
        "Reason: PRICING. unit cost variance.",
        claimed_unit_price=5.0,
        invoice_unit_price=5.0,
        po_unit_price=5.0,
    )
    assert result.resolved is True
    assert result.is_valid is False
