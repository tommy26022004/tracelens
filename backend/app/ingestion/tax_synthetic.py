"""Five-page synthetic Malaysian Form C company tax-return generator."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.ingestion.coherent_financials import CoherentFinancials, default_coherent_financials
from app.ingestion.pdf_layout import (
    LEFT,
    RIGHT,
    draw_key_values,
    draw_page_frame,
    draw_section,
    draw_table,
    draw_title,
)
from app.ingestion.types import TaxReturn

PAGE_COUNT = 5


@dataclass(frozen=True)
class TaxReturnGeneratorConfig:
    company_name: str = "ACME TRADING SDN BHD"
    tax_reference_number: str = "C 1234567890"
    year_of_assessment: int = 2025
    gross_business_income: Decimal = Decimal("1800000.00")
    chargeable_income: Decimal = Decimal("249000.00")
    tax_rate: Decimal = Decimal("0.24")


def _profile_from_config(cfg: TaxReturnGeneratorConfig) -> CoherentFinancials:
    return default_coherent_financials().with_changes(
        company_name=cfg.company_name,
        bank_account_holder=cfg.company_name,
        audited_company_name=cfg.company_name,
        tax_company_name=cfg.company_name,
        tax_reference_number=cfg.tax_reference_number,
        financial_year_end=default_coherent_financials().financial_year_end.replace(
            year=cfg.year_of_assessment
        ),
        tax_gross_business_income=cfg.gross_business_income,
        tax_chargeable_income=cfg.chargeable_income,
    )


def build_tax_return(
    cfg: TaxReturnGeneratorConfig,
    coherent: CoherentFinancials | None = None,
) -> TaxReturn:
    profile = coherent or _profile_from_config(cfg)
    return TaxReturn(
        company_name=profile.tax_company_name,
        tax_reference_number=profile.tax_reference_number,
        year_of_assessment=profile.financial_year_end.year,
        gross_business_income=profile.tax_gross_business_income,
        chargeable_income=profile.tax_chargeable_income,
        tax_payable=profile.tax_payable,
        page_count=PAGE_COUNT,
    )


def _frame(
    c: canvas.Canvas,
    tax: TaxReturn,
    page: int,
    title: str,
    page_count: int,
) -> None:
    draw_page_frame(c, tax.company_name, "FORM C - COMPANY TAX RETURN", page, page_count)
    c.setFillColor(colors.HexColor("#475569"))
    c.setFont("Helvetica", 8)
    c.drawRightString(RIGHT, 49, title)


def render_pdf(
    tax: TaxReturn,
    output_path: Path,
    profile: CoherentFinancials | None = None,
    supplemental_pages: int = 0,
) -> Path:
    profile = profile or default_coherent_financials().with_changes(
        tax_company_name=tax.company_name,
        tax_reference_number=tax.tax_reference_number,
        tax_gross_business_income=tax.gross_business_income,
        tax_chargeable_income=tax.chargeable_income,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=A4)
    total_pages = PAGE_COUNT + supplemental_pages

    _frame(c, tax, 1, "Form C Cover", total_pages)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(A4[0] / 2, 734, "LEMBAGA HASIL DALAM NEGERI MALAYSIA")
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(A4[0] / 2, 711, "INLAND REVENUE BOARD OF MALAYSIA")
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(A4[0] / 2, 650, "BORANG C / FORM C")
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(A4[0] / 2, 623, "RETURN FORM OF A COMPANY")
    draw_key_values(
        c,
        (
            ("Year of Assessment", str(tax.year_of_assessment)),
            ("Company Name", tax.company_name),
            ("Tax Reference Number", tax.tax_reference_number),
            ("Business Address", profile.business_address),
            ("Return Status", "ORIGINAL RETURN - SYNTHETIC SAMPLE"),
        ),
        565,
    )
    c.showPage()

    _frame(c, tax, 2, "Part A", total_pages)
    y = draw_title(c, "PART A - COMPANY PARTICULARS")
    authorised_signatory = (
        "INFORMATION NOT PROVIDED"
        if "tax.authorized_signatory" in profile.missing_fields
        else profile.directors[0].name
    )
    draw_key_values(
        c,
        (
            ("Company Name", tax.company_name),
            ("Business Registration No.", profile.registration_number),
            ("Nature of Business", profile.business_nature),
            (
                "Accounting Period",
                f"01 January {tax.year_of_assessment} to 31 December {tax.year_of_assessment}",
            ),
            ("Auditor", f"{profile.auditor} ({profile.auditor_number})"),
            ("Authorised Signatory", authorised_signatory),
            ("Registered Address", profile.registered_office),
        ),
        y,
    )
    c.showPage()

    _frame(c, tax, 3, "Part B", total_pages)
    y = draw_title(c, "PART B - INCOME COMPUTATION SUMMARY", "Amounts in Ringgit Malaysia")
    allowable_other = max(
        tax.gross_business_income
        - profile.salaries
        - profile.rental_expense
        - profile.depreciation
        - tax.chargeable_income,
        Decimal(0),
    )
    balance = tax.tax_payable - profile.tax_instalments_paid
    computation_rows = (
        ("Gross Business Income", f"RM {tax.gross_business_income:,.2f}"),
        ("Less: Salaries", f"RM {profile.salaries:,.2f}"),
        ("Less: Rental", f"RM {profile.rental_expense:,.2f}"),
        ("Less: Capital Allowance", f"RM {profile.depreciation:,.2f}"),
        ("Less: Other Deductions", f"RM {allowable_other:,.2f}"),
        ("Adjusted Income", f"RM {tax.chargeable_income:,.2f}"),
        ("Statutory Income", f"RM {tax.chargeable_income:,.2f}"),
        ("Chargeable Income", f"RM {tax.chargeable_income:,.2f}"),
        ("Tax Payable", f"RM {tax.tax_payable:,.2f}"),
        ("Less: Tax Instalments Paid", f"RM {profile.tax_instalments_paid:,.2f}"),
        ("Balance Payable / (Refundable)", f"RM {balance:,.2f}"),
    )
    draw_key_values(c, computation_rows, y, 230, 24)
    c.showPage()

    _frame(c, tax, 4, "Capital Allowance Schedule", total_pages)
    y = draw_title(c, "CAPITAL ALLOWANCE SCHEDULE")
    if "tax.capital_allowance_schedule" in profile.missing_fields:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(LEFT, y - 25, "INFORMATION NOT PROVIDED BY APPLICANT")
    else:
        asset_rows = (
            ("Motor Vehicles", "180,000.00", "36,000.00", "36,000.00", "108,000.00"),
            ("Office Equipment", "80,000.00", "16,000.00", "8,000.00", "56,000.00"),
            ("Computer Equipment", "30,000.00", "6,000.00", "6,000.00", "18,000.00"),
        )
        draw_table(
            c,
            ("Asset", "Cost", "Initial Allow.", "Annual Allow.", "Residual Value"),
            asset_rows,
            (142, 83, 92, 92, 83),
            y,
            28,
            ("left", "right", "right", "right", "right"),
            7.5,
        )
    c.showPage()

    _frame(c, tax, 5, "Declaration", total_pages)
    y = draw_title(c, "DECLARATION")
    y = draw_section(c, "DECLARATION BY AUTHORISED PERSON", y)
    c.setFont("Helvetica", 10)
    c.drawString(
        LEFT + 7,
        y,
        "I hereby declare that the information given in this return is true and correct",
    )
    c.drawString(LEFT + 7, y - 22, "to the best of my knowledge and belief.")
    signatory = profile.directors[0]
    draw_key_values(
        c,
        (
            ("Director Name", signatory.name),
            ("IC No.", signatory.nric_or_passport or "N/A"),
            ("Designation", signatory.role or "Director"),
            ("Date", f"{profile.audit_date:%d %B %Y}"),
        ),
        y - 70,
    )
    c.line(LEFT, 225, LEFT + 190, 225)
    c.drawString(LEFT, 210, "Signature")
    c.rect(RIGHT - 150, 170, 150, 95, fill=0, stroke=1)
    c.drawCentredString(RIGHT - 75, 211, "COMPANY STAMP")
    c.showPage()
    schedule_topics = (
        "Business Income Computation",
        "Allowable Expenses",
        "Capital Allowances",
        "Tax Instalment Reconciliation",
        "Related Party Disclosure",
    )
    for page_number in range(PAGE_COUNT + 1, total_pages + 1):
        topic = schedule_topics[(page_number - PAGE_COUNT - 1) % len(schedule_topics)]
        _frame(c, tax, page_number, topic, total_pages)
        y = draw_title(c, topic.upper(), f"Year of Assessment {tax.year_of_assessment}")
        rows = [
            (
                f"Schedule item {index:02d}",
                f"RM {tax.gross_business_income / Decimal(index + 7):,.2f}",
                "Supporting computation",
            )
            for index in range(1, 13)
        ]
        draw_table(
            c,
            ("Description", "Amount", "Tax treatment"),
            rows,
            (230, 115, 147),
            y,
            27,
            ("left", "right", "left"),
            8,
        )
        c.showPage()
    c.save()
    return output_path


def generate(
    cfg: TaxReturnGeneratorConfig,
    out_dir: Path,
    coherent: CoherentFinancials | None = None,
) -> tuple[Path, Path]:
    profile = coherent or _profile_from_config(cfg)
    tax = build_tax_return(cfg, profile)
    pdf_path = out_dir / "tax_return.pdf"
    render_pdf(tax, pdf_path, profile)
    json_path = pdf_path.with_suffix(".ground_truth.json")
    json_path.write_text(tax.model_dump_json(indent=2), encoding="utf-8")
    return pdf_path, json_path


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/samples")
    pdf, ground_truth = generate(TaxReturnGeneratorConfig(), target)
    print(f"PDF:          {pdf}")
    print(f"Ground truth: {ground_truth}")
