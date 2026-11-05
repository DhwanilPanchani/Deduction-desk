"""Unit tests for synthetic document generation and extraction."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent.document_extractor import DocumentExtractor, ExtractedDeduction, _clean_amount, _normalize_type
from agent.document_generator import DocumentGenerator
from agent.llm_provider import LLMProvider


class DummyExtractorProvider(LLMProvider):
    def __init__(self, response_json: str) -> None:
        super().__init__()
        self.response_json = response_json
        self.prompts: list[str] = []

    def call_llm(self, prompt: str, temperature: float = 0.7) -> str:
        self.prompts.append(prompt)
        return self.response_json


@pytest.fixture
def sample_row() -> dict:
    return {
        "deduction_id": 999,
        "deduction_number": "DED-0000999",
        "deduction_type": "shortage",
        "claimed_amount": 125.50,
        "claim_date": "2026-03-01",
        "retailer_notes": "Hi team, short shipment on PO-2601-000999",
        "invoice_id": 100,
        "invoice_number": "INV-2601-000100",
        "invoice_date": "2026-02-28",
        "invoice_gross": 2500.00,
        "po_number": "PO-2601-000999",
        "order_date": "2026-02-20",
        "retailer_name": "Walmart",
        "retailer_code": "WMT",
        "brand_name": "Test Brands Co",
        "remittance_number": "REM-2603-000500",
        "remittance_date": "2026-03-05",
        "paid_amount": 2374.50,
        "invoice_amount": 2500.00,
    }


def test_clean_amount_and_normalize_type() -> None:
    assert _clean_amount("$1,234.56") == Decimal("1234.56")
    assert _clean_amount("45.00") == Decimal("45.00")
    assert _clean_amount(None) is None

    assert _normalize_type("SHORTAGE CLAIM") == "shortage"
    assert _normalize_type("PRICING_DISCREPANCY") == "pricing"
    assert _normalize_type("Vendor Allowance Promo") == "promotional"
    assert _normalize_type("OTIF Late Compliance") == "compliance"
    assert _normalize_type("Damaged Goods in Transit") == "damage"


def test_generate_and_extract_all_retailers(tmp_path: Path, sample_row: dict) -> None:
    generator = DocumentGenerator(output_dir=tmp_path)
    extractor = DocumentExtractor()

    for retailer, code in [
        ("Walmart", "WMT"),
        ("Target", "TGT"),
        ("Costco", "COST"),
        ("Kroger", "KRO"),
    ]:
        row = dict(sample_row)
        row["retailer_name"] = retailer
        row["retailer_code"] = code
        pdf_file = tmp_path / f"test_{code}.pdf"

        meta = generator.generate_pdf(row, pdf_file)
        assert pdf_file.exists()
        assert pdf_file.stat().st_size > 500
        assert meta["po_number"] == row["po_number"]

        # Test non-LLM extraction on generated PDF
        extracted = extractor.extract_non_llm(pdf_file)
        assert extracted.po_number == row["po_number"]
        assert extracted.invoice_number == row["invoice_number"]
        assert extracted.claimed_amount == Decimal("125.50")
        assert extracted.deduction_type == "shortage"
        assert extracted.extraction_method == "table"


def test_llm_extraction_path_mock(tmp_path: Path, sample_row: dict) -> None:
    generator = DocumentGenerator(output_dir=tmp_path)
    pdf_file = tmp_path / "mock_llm.pdf"
    generator.generate_pdf(sample_row, pdf_file)

    mock_llm_response = json.dumps(
        {
            "po_number": sample_row["po_number"],
            "invoice_number": sample_row["invoice_number"],
            "claimed_amount": 125.50,
            "deduction_type": "shortage",
            "retailer_notes": sample_row["retailer_notes"],
        }
    )
    dummy_provider = DummyExtractorProvider(mock_llm_response)
    extractor = DocumentExtractor(provider=dummy_provider)

    extracted = extractor.extract_with_llm(pdf_file)

    assert extracted.extraction_method == "llm"
    assert extracted.po_number == sample_row["po_number"]
    assert extracted.invoice_number == sample_row["invoice_number"]
    assert extracted.claimed_amount == Decimal("125.50")
    assert extracted.deduction_type == "shortage"
    assert len(dummy_provider.prompts) == 1
    assert "PO-2601-000999" in dummy_provider.prompts[0]

