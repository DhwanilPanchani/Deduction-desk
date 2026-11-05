"""Document extraction module for retailer remittances with non-LLM and LLM paths."""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

import pdfplumber
from pydantic import BaseModel, Field

from .config import Settings, settings
from .llm_classifier import _extract_json
from .llm_provider import LLMProvider, get_provider

logger = logging.getLogger(__name__)


class ExtractedDeduction(BaseModel):
    """Normalized structured data extracted from a remittance document."""

    po_number: str | None = None
    invoice_number: str | None = None
    claimed_amount: Decimal | None = None
    deduction_type: str | None = None
    retailer_notes: str | None = None
    extraction_method: Literal["table", "regex_fallback", "llm"]
    raw_text: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    error: str | None = None


def _clean_amount(raw_val: Any) -> Decimal | None:
    if raw_val is None:
        return None
    cleaned = str(raw_val).replace("$", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        match = re.search(r"(\d+(?:\.\d{2})?)", cleaned)
        if match:
            return Decimal(match.group(1))
    return None


def _normalize_type(raw_val: Any) -> str | None:
    if not raw_val:
        return None
    text = str(raw_val).lower().strip()
    if "promo" in text or "allowance" in text:
        return "promotional"
    if "short" in text or "qty" in text:
        return "shortage"
    if "price" in text or "pricing" in text or "cost" in text or "variance" in text:
        return "pricing"
    if "compl" in text or "late" in text or "otif" in text:
        return "compliance"
    if "damage" in text or "dmg" in text:
        return "damage"
    return text


class DocumentExtractor:
    """Extracts deduction fields from PDF remittances via non-LLM or LLM paths."""

    def __init__(
        self,
        config: Settings = settings,
        provider: LLMProvider | None = None,
    ) -> None:
        self.config = config
        self.provider = provider

    def _get_provider(self) -> LLMProvider:
        if self.provider is None:
            self.provider = get_provider(self.config)
        return self.provider

    # =========================================================================
    # PATH 1: Non-LLM extraction using pdfplumber (Fast, free, deterministic)
    # =========================================================================
    def extract_non_llm(self, pdf_path: Path | str) -> ExtractedDeduction:
        """Extract structured fields using table extraction with regex fallback.

        Requires no external API calls. Runs fully local and deterministic.
        """
        path = Path(pdf_path)
        if not path.exists():
            return ExtractedDeduction(
                extraction_method="table",
                confidence=0.0,
                error=f"File not found: {path}",
            )

        raw_text_parts: list[str] = []
        tables: list[list[list[str | None]]] = []

        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    raw_text_parts.append(text)
                extracted_tables = page.extract_tables()
                if extracted_tables:
                    tables.extend(extracted_tables)

        full_raw_text = "\n".join(raw_text_parts)

        # Attempt 1: Tabular extraction
        if tables:
            for table in tables:
                extracted = self._parse_table(table, full_raw_text)
                if (
                    extracted.po_number
                    and extracted.invoice_number
                    and extracted.claimed_amount is not None
                ):
                    return extracted

        # Attempt 2: Text regex fallback
        return self._parse_regex_fallback(full_raw_text)

    def _parse_table(
        self, table: list[list[str | None]], raw_text: str
    ) -> ExtractedDeduction:
        if not table or len(table) < 2:
            return ExtractedDeduction(extraction_method="table", confidence=0.0)

        header_row = [str(c or "").strip().lower() for c in table[0]]

        po_idx = self._find_col(
            header_row,
            ["po number", "po_no", "purchase_order", "po #", "po"],
        )
        inv_idx = self._find_col(
            header_row,
            ["invoice ref", "inv_no", "invoice_no", "invoice #", "invoice"],
        )
        amt_idx = self._find_col(
            header_row,
            ["amount claimed", "amount", "deducted_amt", "amount ($)", "claim amount ($)"],
        )
        type_idx = self._find_col(
            header_row,
            ["category", "claim_type", "adj_type", "adj type", "adjustment_type", "reason type", "type"],
        )
        notes_idx = self._find_col(
            header_row,
            ["retailer notes", "details", "adjustment_reason", "remarks", "notes"],
        )

        # Read first data row
        data_row = table[1]
        raw_po = data_row[po_idx].strip() if po_idx is not None and po_idx < len(data_row) and data_row[po_idx] else None
        raw_inv = data_row[inv_idx].strip() if inv_idx is not None and inv_idx < len(data_row) and data_row[inv_idx] else None
        
        # Clean PO and Invoice patterns if OCR/cell spacing caused overlapping characters
        po_val = None
        if raw_po:
            po_match = re.search(r"PO-\d{4}-\d{6}", raw_po)
            po_val = po_match.group(0) if po_match else raw_po

        inv_val = None
        if raw_inv:
            inv_match = re.search(r"INV-\d{4}-\d{6}", raw_inv)
            inv_val = inv_match.group(0) if inv_match else raw_inv

        amt_val = _clean_amount(data_row[amt_idx]) if amt_idx is not None and amt_idx < len(data_row) else None
        type_val = _normalize_type(data_row[type_idx]) if type_idx is not None and type_idx < len(data_row) else None
        notes_val = str(data_row[notes_idx]).strip() if notes_idx is not None and notes_idx < len(data_row) and data_row[notes_idx] else None

        return ExtractedDeduction(
            po_number=po_val,
            invoice_number=inv_val,
            claimed_amount=amt_val,
            deduction_type=type_val,
            retailer_notes=notes_val,
            extraction_method="table",
            raw_text=raw_text,
            confidence=0.98 if (po_val and inv_val and amt_val) else 0.5,
        )

    def _find_col(self, headers: list[str], candidates: list[str]) -> int | None:
        for idx, h in enumerate(headers):
            for cand in candidates:
                if cand in h:
                    return idx
        return None

    def _parse_regex_fallback(self, raw_text: str) -> ExtractedDeduction:
        po_match = re.search(r"\b(PO-\d{4}-\d{6})\b", raw_text)
        inv_match = re.search(r"\b(INV-\d{4}-\d{6})\b", raw_text)
        amt_match = re.search(r"\$\s*([0-9,]+(?:\.[0-9]{2})?)", raw_text)

        deduction_type = None
        for cat in ("shortage", "pricing", "promotional", "compliance", "damage"):
            if re.search(rf"\b{cat}\b", raw_text, re.IGNORECASE):
                deduction_type = cat
                break

        amount = _clean_amount(amt_match.group(1)) if amt_match else None

        return ExtractedDeduction(
            po_number=po_match.group(1) if po_match else None,
            invoice_number=inv_match.group(1) if inv_match else None,
            claimed_amount=amount,
            deduction_type=deduction_type,
            retailer_notes=None,
            extraction_method="regex_fallback",
            raw_text=raw_text,
            confidence=0.85 if (po_match and inv_match and amount) else 0.4,
        )

    # =========================================================================
    # PATH 2: LLM-based extraction (Wired, prompt-ready, unexecuted today)
    # =========================================================================
    def build_llm_prompt(self, raw_text: str) -> str:
        """Construct a structured JSON extraction prompt for messy or garbled documents."""
        return f"""You are an expert accounts payable document parser.
Extract the retailer deduction claim details from the following remittance document text:

--- REMITTANCE DOCUMENT TEXT ---
{raw_text}
--- END DOCUMENT TEXT ---

Extract the exact fields and return strict JSON only:
{{
    "po_number": "PO-XXXX-XXXXXX or null",
    "invoice_number": "INV-XXXX-XXXXXX or null",
    "claimed_amount": 123.45,
    "deduction_type": "shortage|pricing|promotional|compliance|damage",
    "retailer_notes": "Extracted retailer notes, explanation or remarks"
}}
"""

    def extract_with_llm(self, pdf_path: Path | str) -> ExtractedDeduction:
        """Extract structured fields using an LLM provider.

        NOTE: Ready to test, not yet run.
        """
        path = Path(pdf_path)
        raw_text_parts: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    raw_text_parts.append(text)
        raw_text = "\n".join(raw_text_parts)

        prompt = self.build_llm_prompt(raw_text)
        provider = self._get_provider()

        response_str = provider.call_llm(prompt, temperature=0.0)
        parsed_dict = _extract_json(response_str)

        return ExtractedDeduction(
            po_number=parsed_dict.get("po_number"),
            invoice_number=parsed_dict.get("invoice_number"),
            claimed_amount=_clean_amount(parsed_dict.get("claimed_amount")),
            deduction_type=_normalize_type(parsed_dict.get("deduction_type")),
            retailer_notes=parsed_dict.get("retailer_notes"),
            extraction_method="llm",
            raw_text=raw_text,
            confidence=0.90,
        )
