"""Generate synthetic retailer remittance documents (PDFs) with realistic format variance."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .config import Settings, settings

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic_remittances"


class DocumentGenerator:
    """Generates synthetic PDF remittances simulating real-world retailer variance."""

    def __init__(
        self,
        config: Settings = settings,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch_sample_deductions(self, limit: int = 25) -> list[dict[str, Any]]:
        """Fetch a diverse sample of deductions across retailers and categories from the database."""
        conn = psycopg2.connect(self.config.database_url)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT d.id AS deduction_id,
                       d.deduction_number,
                       d.type AS deduction_type,
                       d.amount AS claimed_amount,
                       d.claim_date,
                       d.retailer_notes,
                       d.invoice_id,
                       i.invoice_number,
                       i.invoice_date,
                       i.gross_amount AS invoice_gross,
                       po.po_number,
                       po.order_date,
                       r.name AS retailer_name,
                       r.retailer_code,
                       b.name AS brand_name,
                       rem.remittance_number,
                       rem.remittance_date,
                       rem.paid_amount,
                       rem.invoice_amount
                FROM deductions d
                JOIN invoices i ON i.id = d.invoice_id
                JOIN purchase_orders po ON po.id = i.purchase_order_id
                JOIN retailers r ON r.id = po.retailer_id
                JOIN brands b ON b.id = po.brand_id
                JOIN remittances rem ON rem.id = d.remittance_id
                ORDER BY d.id
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def generate_pdf(
        self, row: dict[str, Any], filepath: Path, difficulty: str = "clean"
    ) -> dict[str, Any]:
        """Render a single retailer remittance PDF with retailer-specific styling."""
        if difficulty == "hard":
            return self._render_hard_memo_pdf(row, filepath)

        retailer = row["retailer_name"].lower()
        if "walmart" in retailer:
            return self._render_walmart_pdf(row, filepath)
        elif "target" in retailer:
            return self._render_target_pdf(row, filepath)
        elif "costco" in retailer:
            return self._render_costco_pdf(row, filepath)
        else:
            return self._render_kroger_pdf(row, filepath)

    def _render_walmart_pdf(self, row: dict[str, Any], filepath: Path) -> dict[str, Any]:
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )
        styles = getSampleStyleSheet()
        elements = []

        # Walmart Header
        header_style = ParagraphStyle(
            "WmtHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            textColor=colors.HexColor("#0071CE"),
            spaceAfter=4,
        )
        sub_style = ParagraphStyle(
            "WmtSub",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            textColor=colors.HexColor("#333333"),
        )
        cell_style = ParagraphStyle(
            "WmtCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
        )

        elements.append(Paragraph("WALMART INC. — AP REMITTANCE ADVICE", header_style))
        elements.append(
            Paragraph(
                f"Remittance Ref: <b>{row['remittance_number']}</b> | Date: {row['remittance_date']} | Supplier: {row['brand_name']}",
                sub_style,
            )
        )
        elements.append(Spacer(1, 10))
        elements.append(
            HRFlowable(width="100%", thickness=2, color=colors.HexColor("#FFC220"), spaceAfter=14)
        )

        table_data = [
            [
                "Claim Ref",
                "PO Number",
                "Invoice Ref",
                "Category",
                "Amount Claimed",
                "Retailer Notes",
            ],
            [
                row["deduction_number"],
                row["po_number"],
                row["invoice_number"],
                row["deduction_type"].upper(),
                f"${Decimal(str(row['claimed_amount'])):,.2f}",
                Paragraph(row["retailer_notes"] or "None", cell_style),
            ],
        ]

        t = Table(table_data, colWidths=[75, 95, 95, 75, 75, 125])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0071CE")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F2F8FC")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B0C8DD")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(t)
        doc.build(elements)
        return self._make_meta(row, filepath, layout_type="structured_table", difficulty_tier="clean")

    def _render_target_pdf(self, row: dict[str, Any], filepath: Path) -> dict[str, Any]:
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )
        styles = getSampleStyleSheet()
        elements = []

        header_style = ParagraphStyle(
            "TgtHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=colors.HexColor("#CC0000"),
            spaceAfter=4,
        )
        sub_style = ParagraphStyle(
            "TgtSub",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#555555"),
        )
        cell_style = ParagraphStyle(
            "TgtCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
        )

        elements.append(Paragraph("TARGET CORP. // DISBURSEMENT DETAIL", header_style))
        elements.append(
            Paragraph(
                f"VOUCHER #{row['remittance_number']} // DISBURSEMENT DATE: {row['remittance_date']} // VENDOR: {row['brand_name']}",
                sub_style,
            )
        )
        elements.append(Spacer(1, 10))
        elements.append(
            HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#CC0000"), spaceAfter=14)
        )

        table_data = [
            [
                "CLAIM_ID",
                "PURCHASE_ORDER",
                "INVOICE_NO",
                "ADJ_TYPE",
                "DEDUCTED_AMT",
                "REASON_SUMMARY",
            ],
            [
                row["deduction_number"],
                row["po_number"],
                row["invoice_number"],
                row["deduction_type"],
                f"${Decimal(str(row['claimed_amount'])):,.2f}",
                Paragraph(row["retailer_notes"] or "", cell_style),
            ],
        ]

        t = Table(table_data, colWidths=[75, 95, 95, 75, 75, 125])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("LINEBELOW", (0, 1), (-1, 1), 1, colors.HexColor("#CC0000")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(t)
        doc.build(elements)
        return self._make_meta(row, filepath, layout_type="structured_table", difficulty_tier="clean")

    def _render_costco_pdf(self, row: dict[str, Any], filepath: Path) -> dict[str, Any]:
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )
        styles = getSampleStyleSheet()
        elements = []

        header_style = ParagraphStyle(
            "CostcoHeader",
            parent=styles["Normal"],
            fontName="Courier-Bold",
            fontSize=13,
            textColor=colors.HexColor("#005DAA"),
            spaceAfter=3,
        )
        sub_style = ParagraphStyle(
            "CostcoSub",
            parent=styles["Normal"],
            fontName="Courier",
            fontSize=8,
            textColor=colors.black,
        )
        cell_style = ParagraphStyle(
            "CostcoCell",
            parent=styles["Normal"],
            fontName="Courier",
            fontSize=7.5,
            leading=9,
        )

        elements.append(Paragraph("COSTCO WHOLESALE - VENDOR SETTLEMENT STATEMENT", header_style))
        elements.append(
            Paragraph(
                f"STMT-REF: {row['remittance_number']}   DATE: {row['remittance_date']}   ACCT: {row['brand_name']}",
                sub_style,
            )
        )
        elements.append(Spacer(1, 8))
        elements.append(
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E31837"), spaceAfter=12)
        )

        table_data = [
            ["ADJ_CODE", "PO_NO", "INV_NO", "CLAIM_TYPE", "AMOUNT", "DETAILS"],
            [
                row["deduction_number"],
                row["po_number"],
                row["invoice_number"],
                row["deduction_type"].upper(),
                f"${Decimal(str(row['claimed_amount'])):,.2f}",
                Paragraph(row["retailer_notes"] or "N/A", cell_style),
            ],
        ]

        t = Table(table_data, colWidths=[75, 95, 95, 75, 75, 125])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#005DAA")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(t)
        doc.build(elements)
        return self._make_meta(row, filepath, layout_type="structured_table", difficulty_tier="clean")

    def _render_kroger_pdf(self, row: dict[str, Any], filepath: Path) -> dict[str, Any]:
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )
        styles = getSampleStyleSheet()
        elements = []

        header_style = ParagraphStyle(
            "KrogerHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=colors.HexColor("#1B4998"),
            spaceAfter=3,
        )
        sub_style = ParagraphStyle(
            "KrogerSub",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#444444"),
        )
        cell_style = ParagraphStyle(
            "KrogerCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
        )

        elements.append(Paragraph("THE KROGER CO. — AP REMITTANCE VOUCHER", header_style))
        elements.append(
            Paragraph(
                f"Voucher ID: {row['remittance_number']} | Date: {row['remittance_date']} | Payee: {row['brand_name']}",
                sub_style,
            )
        )
        elements.append(Spacer(1, 8))
        elements.append(
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1B4998"), spaceAfter=12)
        )

        table_data = [
            ["Deduction No", "PO #", "Invoice No", "Reason Type", "Claim Amount ($)", "Remarks"],
            [
                row["deduction_number"],
                row["po_number"],
                row["invoice_number"],
                row["deduction_type"],
                f"${Decimal(str(row['claimed_amount'])):,.2f}",
                Paragraph(row["retailer_notes"] or "", cell_style),
            ],
        ]

        t = Table(table_data, colWidths=[75, 95, 95, 75, 75, 125])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B4998")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F9F9F9")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(t)
        doc.build(elements)
        return self._make_meta(row, filepath, layout_type="structured_table", difficulty_tier="clean")

    def _render_hard_memo_pdf(self, row: dict[str, Any], filepath: Path) -> dict[str, Any]:
        """Render an unstructured, narrative discrepancy debit memo (hard tier).

        These documents do not contain formatted tables and use flowing prose with
        multiple conflicting dollar values (gross invoice, net payment, deduction)
        and operational jargon to simulate messy real-world retailer remittances.
        """
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            leftMargin=40,
            rightMargin=40,
            topMargin=40,
            bottomMargin=40,
        )
        styles = getSampleStyleSheet()
        elements = []

        retailer = row["retailer_name"].lower()
        if "walmart" in retailer:
            brand_color = colors.HexColor("#0071CE")
            header_title = "WALMART INC. — AP DISCREPANCY ADVICE MEMO"
        elif "target" in retailer:
            brand_color = colors.HexColor("#CC0000")
            header_title = "TARGET CORP. — AP SETTLEMENT CHARGEBACK MEMORANDUM"
        elif "costco" in retailer:
            brand_color = colors.HexColor("#005DAA")
            header_title = "COSTCO WHOLESALE — ACCOUNTS PAYABLE DISCREPANCY NOTICE"
        else:
            brand_color = colors.HexColor("#1B4998")
            header_title = "THE KROGER CO. — AP AUDIT & DISPUTE NOTIFICATION"

        header_style = ParagraphStyle(
            "HardHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=brand_color,
            spaceAfter=4,
        )
        sub_style = ParagraphStyle(
            "HardSub",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#444444"),
        )
        section_style = ParagraphStyle(
            "HardSection",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.HexColor("#222222"),
            spaceBefore=6,
            spaceAfter=3,
        )
        body_style = ParagraphStyle(
            "HardBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#333333"),
        )

        elements.append(Paragraph(header_title, header_style))
        elements.append(
            Paragraph(
                f"Settlement Ref: <b>{row['remittance_number']}</b> &nbsp;|&nbsp; Date: {row['remittance_date']} &nbsp;|&nbsp; Vendor: {row['brand_name']}",
                sub_style,
            )
        )
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=brand_color, spaceAfter=12))

        claimed = Decimal(str(row["claimed_amount"]))
        gross = Decimal(str(row.get("invoice_gross") or (claimed * Decimal("3.5"))))
        paid = gross - claimed

        # Settlement Audit Section (Multiple dollar amounts in prose)
        elements.append(Paragraph("<b>SETTLEMENT AUDIT BREAKDOWN</b>", section_style))
        elements.append(
            Paragraph(
                f"Original Gross Invoice Billing: <b>${gross:,.2f}</b><br/>"
                f"Disbursed Settlement Payment: <b>${paid:,.2f}</b><br/>"
                f"Assessed Deduction Discrepancy: <b>${claimed:,.2f}</b>",
                body_style,
            )
        )
        elements.append(Spacer(1, 8))

        # References in narrative prose
        elements.append(Paragraph("<b>TRANSACTION & ORDER REFERENCES</b>", section_style))
        elements.append(
            Paragraph(
                f"This debit memo applies against vendor billing invoice <b>{row['invoice_number']}</b> "
                f"(dated {row['invoice_date']}), issued under authorized customer purchase order <b>{row['po_number']}</b> "
                f"(order date {row['order_date']}). Deduction reference number: {row['deduction_number']}.",
                body_style,
            )
        )
        elements.append(Spacer(1, 8))

        # Discrepancy narrative
        dtype = str(row["deduction_type"]).lower()
        if "shortage" in dtype:
            narrative = (
                "Receiving Discrepancy: Physical dock receiving count conducted at destination distribution "
                "center identified a shipment quantity deficit against quantities billed on vendor packing slip. "
                "Inbound merchandise short-shipped."
            )
        elif "pricing" in dtype:
            narrative = (
                "Unit Rate Discrepancy: Billed invoice unit price exceeds agreed contract pricing confirmed on "
                "authorized purchase order line items. Variance deducted from invoice settlement balance."
            )
        elif "promo" in dtype:
            narrative = (
                "Merchandising Co-Op Promotion: Agreed joint business advertising allowance and weekly circular "
                "feature promotion credit deducted in accordance with seasonal marketing agreement."
            )
        elif "compl" in dtype:
            narrative = (
                "Logistics Vendor Compliance Fee: Inbound carrier missed scheduled appointment arrival window and "
                "ASN electronic advance delivery notification was late. OTIF operational penalty assessed."
            )
        elif "damage" in dtype:
            narrative = (
                "Damaged Product Notice: Receiving inspector identified compromised product packaging, crushed "
                "master cases, and unsaleable merchandise rejected at receiving dock."
            )
        else:
            narrative = f"Audit Discrepancy: Assessed deduction chargeback under category {dtype}."

        elements.append(Paragraph("<b>DISCREPANCY FINDINGS & AUDIT JUSTIFICATION</b>", section_style))
        elements.append(Paragraph(narrative, body_style))
        elements.append(Spacer(1, 8))

        notes = (
            row.get("retailer_notes")
            or "Automated accounts payable audit discrepancy applied per trading agreement."
        )
        elements.append(Paragraph("<b>AUDITOR NOTES & REMARKS</b>", section_style))
        elements.append(Paragraph(str(notes), body_style))

        doc.build(elements)
        return self._make_meta(row, filepath, layout_type="narrative_memo", difficulty_tier="hard")

    def _make_meta(
        self,
        row: dict[str, Any],
        filepath: Path,
        layout_type: str,
        difficulty_tier: str = "clean",
    ) -> dict[str, Any]:
        return {
            "deduction_id": row["deduction_id"],
            "deduction_number": row["deduction_number"],
            "filename": filepath.name,
            "filepath": str(filepath),
            "retailer_name": row["retailer_name"],
            "po_number": row["po_number"],
            "invoice_number": row["invoice_number"],
            "deduction_type": row["deduction_type"],
            "claimed_amount": float(row["claimed_amount"]),
            "retailer_notes": row["retailer_notes"],
            "layout_type": layout_type,
            "difficulty_tier": difficulty_tier,
        }

    def generate_batch(self, count: int = 25, split_tiers: bool = True) -> list[dict[str, Any]]:
        """Generate N synthetic PDFs and save ground truth metadata index.

        When split_tiers=True, generates a mixed-difficulty set:
        - Clean tier: structured tabular remittances
        - Hard tier: unstructured narrative discrepancy memos
        """
        rows = self.fetch_sample_deductions(limit=count)
        metadata_list: list[dict[str, Any]] = []

        # Clean existing remittance PDFs in output_dir to prevent orphan files
        for old_pdf in self.output_dir.glob("remittance_*.pdf"):
            try:
                old_pdf.unlink()
            except OSError:
                pass

        half = (len(rows) + 1) // 2

        for idx, row in enumerate(rows):
            tier = "clean" if (not split_tiers or idx < half) else "hard"
            filename = (
                f"remittance_deduction_{row['deduction_id']:04d}_{row['retailer_code']}_{tier}.pdf"
            )
            filepath = self.output_dir / filename
            meta = self.generate_pdf(row, filepath, difficulty=tier)
            metadata_list.append(meta)

        # Write ground truth JSON index
        gt_path = self.output_dir / "ground_truth.json"
        with open(gt_path, "w") as f:
            json.dump(metadata_list, f, indent=2)

        return metadata_list
