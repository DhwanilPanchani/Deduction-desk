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

    def generate_pdf(self, row: dict[str, Any], filepath: Path) -> dict[str, Any]:
        """Render a single retailer remittance PDF with retailer-specific styling."""
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
        return self._make_meta(row, filepath, "structured_table")

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
        return self._make_meta(row, filepath, "structured_table")

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
        return self._make_meta(row, filepath, "structured_table")

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
        return self._make_meta(row, filepath, "structured_table")

    def _make_meta(self, row: dict[str, Any], filepath: Path, layout_type: str) -> dict[str, Any]:
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
        }

    def generate_batch(self, count: int = 25) -> list[dict[str, Any]]:
        """Generate N synthetic PDFs and save ground truth metadata index."""
        rows = self.fetch_sample_deductions(limit=count)
        metadata_list: list[dict[str, Any]] = []

        for row in rows:
            filename = (
                f"remittance_deduction_{row['deduction_id']:04d}_{row['retailer_code']}.pdf"
            )
            filepath = self.output_dir / filename
            meta = self.generate_pdf(row, filepath)
            metadata_list.append(meta)

        # Write ground truth JSON index
        gt_path = self.output_dir / "ground_truth.json"
        with open(gt_path, "w") as f:
            json.dump(metadata_list, f, indent=2)

        return metadata_list
