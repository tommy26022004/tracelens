"""Synthetic Malaysian Form C (corporate tax return) generator.

Simplified: a single page with labelled rows. Real LHDN Form C is far
longer, but the credit-relevant fields (gross business income,
chargeable income, tax payable) live in a small section we replicate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.ingestion.types import TaxReturn

MARGIN_X = 50
TOP_Y = 800
ROW_GAP = 18
HEADER_FONT = ("Helvetica-Bold", 12)
LABEL_FONT = ("Helvetica-Bold", 10)
VALUE_FONT = ("Helvetica", 10)


@dataclass(frozen=True)
class TaxReturnGeneratorConfig:
    company_name: str = "ACME TRADING SDN BHD"
    tax_reference_number: str = "C 2500001234"
    year_of_assessment: int = 2025
    gross_business_income: Decimal = Decimal("1750000.00")
    chargeable_income: Decimal = Decimal("420000.00")
    tax_payable: Decimal = Decimal("100800.00")


def build_tax_return(cfg: TaxReturnGeneratorConfig) -> TaxReturn:
    return TaxReturn(
        company_name=cfg.company_name,
        tax_reference_number=cfg.tax_reference_number,
        year_of_assessment=cfg.year_of_assessment,
        gross_business_income=cfg.gross_business_income,
        chargeable_income=cfg.chargeable_income,
        tax_payable=cfg.tax_payable,
        page_count=1,
    )


def _draw_field(c: canvas.Canvas, y: float, label: str, value: str) -> float:
    c.setFont(*LABEL_FONT)
    c.drawString(MARGIN_X, y, f"{label}:")
    c.setFont(*VALUE_FONT)
    c.drawString(MARGIN_X + 220, y, value)
    return y - ROW_GAP


def render_pdf(tax: TaxReturn, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=A4)

    c.setFont(*HEADER_FONT)
    c.drawString(MARGIN_X, TOP_Y, "LEMBAGA HASIL DALAM NEGERI MALAYSIA")
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN_X, TOP_Y - 14, "FORM C - Income Tax Return (Companies)")
    c.drawString(MARGIN_X, TOP_Y - 28, "(Synthetic LHDN Office - SAMPLE)")
    c.line(MARGIN_X, TOP_Y - 38, MARGIN_X + 480, TOP_Y - 38)

    y = TOP_Y - 60
    y = _draw_field(c, y, "Company Name", tax.company_name)
    y = _draw_field(c, y, "Tax Reference Number", tax.tax_reference_number)
    y = _draw_field(c, y, "Year of Assessment", str(tax.year_of_assessment))
    y -= 6
    c.line(MARGIN_X, y, MARGIN_X + 480, y)
    y -= 16
    y = _draw_field(c, y, "Gross Business Income", f"RM {tax.gross_business_income:,.2f}")
    y = _draw_field(c, y, "Chargeable Income", f"RM {tax.chargeable_income:,.2f}")
    y = _draw_field(c, y, "Tax Payable", f"RM {tax.tax_payable:,.2f}")
    c.save()
    return output_path


def generate(cfg: TaxReturnGeneratorConfig, out_dir: Path) -> tuple[Path, Path]:
    tax = build_tax_return(cfg)
    pdf_path = out_dir / f"tax_return_YA{cfg.year_of_assessment}.pdf"
    render_pdf(tax, pdf_path)
    json_path = pdf_path.with_suffix(".ground_truth.json")
    json_path.write_text(tax.model_dump_json(indent=2))
    return pdf_path, json_path


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/samples")
    pdf, gt = generate(TaxReturnGeneratorConfig(), target)
    print(f"PDF:          {pdf}")
    print(f"Ground truth: {gt}")
