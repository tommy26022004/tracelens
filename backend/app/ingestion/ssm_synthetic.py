"""Five-page synthetic SSM registration package generator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
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
from app.ingestion.types import Director, SSMRegistration

PAGE_COUNT = 5


@dataclass(frozen=True)
class SSMGeneratorConfig:
    seed: int = 42
    company_name: str = "ACME TRADING SDN BHD"
    registration_number: str = "202401000123 (1500123-X)"
    incorporation_date: date = date(2024, 1, 15)
    company_type: str = "SDN BHD"
    business_address: str = "Lot 12-3, Jalan Damansara, 50490 Kuala Lumpur"
    paid_up_capital: Decimal = Decimal("250000.00")
    director_pool: tuple[tuple[str, str], ...] = field(
        default=(
            ("AHMAD BIN ABDULLAH", "850102-14-1234"),
            ("LIM WEI MING", "880515-08-5678"),
            ("RAJESH A/L MURUGAN", "900830-10-9012"),
            ("SITI NURBAYA BINTI HASSAN", "920721-03-3456"),
        )
    )
    director_count: int = 2


def _profile_from_config(cfg: SSMGeneratorConfig) -> CoherentFinancials:
    directors = tuple(
        Director(name=name, nric_or_passport=nric, role="Director")
        for name, nric in cfg.director_pool[: cfg.director_count]
    )
    percentages = tuple([Decimal("100.00") / Decimal(max(len(directors), 1))] * len(directors))
    return default_coherent_financials().with_changes(
        company_name=cfg.company_name,
        bank_account_holder=cfg.company_name,
        audited_company_name=cfg.company_name,
        tax_company_name=cfg.company_name,
        registration_number=cfg.registration_number,
        incorporation_date=cfg.incorporation_date,
        business_address=cfg.business_address,
        paid_up_capital=cfg.paid_up_capital,
        directors=directors,
        shareholder_percentages=percentages,
    )


def build_ssm(
    cfg: SSMGeneratorConfig,
    coherent: CoherentFinancials | None = None,
) -> SSMRegistration:
    profile = coherent or _profile_from_config(cfg)
    return SSMRegistration(
        company_name=profile.company_name,
        registration_number=profile.registration_number,
        incorporation_date=profile.incorporation_date,
        company_type=cfg.company_type,
        business_address=profile.business_address,
        paid_up_capital=profile.paid_up_capital,
        directors=list(profile.directors),
        page_count=PAGE_COUNT,
    )


def _frame(
    c: canvas.Canvas,
    ssm: SSMRegistration,
    page: int,
    title: str,
    page_count: int,
) -> None:
    draw_page_frame(c, ssm.company_name, "SSM REGISTRATION PACKAGE", page, page_count)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawRightString(RIGHT, 49, title)


def render_pdf(
    ssm: SSMRegistration,
    output_path: Path,
    profile: CoherentFinancials | None = None,
    supplemental_pages: int = 0,
) -> Path:
    profile = profile or default_coherent_financials().with_changes(
        company_name=ssm.company_name,
        registration_number=ssm.registration_number,
        incorporation_date=ssm.incorporation_date,
        business_address=ssm.business_address,
        paid_up_capital=ssm.paid_up_capital,
        directors=tuple(ssm.directors),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=A4)
    total_pages = PAGE_COUNT + supplemental_pages

    _frame(c, ssm, 1, "Form 9", total_pages)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(A4[0] / 2, 741, "SURUHANJAYA SYARIKAT MALAYSIA")
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(A4[0] / 2, 718, "COMPANIES COMMISSION OF MALAYSIA")
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(A4[0] / 2, 660, "FORM 9 - CERTIFICATE OF INCORPORATION")
    y = draw_key_values(
        c,
        (
            ("Certificate Number", f"CERT-{ssm.incorporation_date:%Y}-{profile.scenario_id:04d}"),
            ("Company Name", ssm.company_name),
            ("Registration Number", ssm.registration_number),
            ("Date of Incorporation", f"{ssm.incorporation_date:%d %B %Y}"),
            ("Company Type", ssm.company_type),
            ("Business Address", ssm.business_address),
            ("Paid-Up Capital", f"RM {ssm.paid_up_capital:,.2f}"),
        ),
        610,
    )
    c.setFont("Helvetica", 10)
    c.drawString(
        LEFT, y - 35, "This is to certify that the above-named company is incorporated under"
    )
    c.drawString(LEFT, y - 55, "the Companies Act 2016 as a private company limited by shares.")
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(LEFT, 93, "SAMPLE - generated for academic evaluation only")
    c.showPage()

    _frame(c, ssm, 2, "Form 24", total_pages)
    y = draw_title(c, "FORM 24 - RETURN OF ALLOTMENT OF SHARES")
    y = draw_key_values(
        c,
        (
            ("Company Name", ssm.company_name),
            ("Registration Number", ssm.registration_number),
            ("Date of Allotment", f"{ssm.incorporation_date:%d %B %Y}"),
        ),
        y,
    )
    share_rows: list[tuple[str, str, str, str]] = []
    for index, director in enumerate(ssm.directors):
        percentage = (
            profile.shareholder_percentages[index]
            if index < len(profile.shareholder_percentages)
            else Decimal(0)
        )
        shares = ssm.paid_up_capital * percentage / Decimal(100)
        share_rows.append(
            (
                director.name,
                director.nric_or_passport or "N/A",
                f"{shares:,.0f}",
                f"{percentage:.2f}%",
            )
        )
    y -= 30
    y = draw_table(
        c,
        ("Shareholder Name", "IC No", "No. of Shares", "%"),
        share_rows,
        (190, 130, 105, 67),
        y,
        28,
        font_size=8,
    )
    c.line(LEFT, y - 90, LEFT + 190, y - 90)
    c.drawString(LEFT, y - 106, "Director signature")
    c.showPage()

    _frame(c, ssm, 3, "Form 44", total_pages)
    y = draw_title(c, "FORM 44 - NOTICE OF REGISTERED OFFICE")
    draw_key_values(
        c,
        (
            ("Company Name", ssm.company_name),
            ("Registration Number", ssm.registration_number),
            ("Registered Office Address", profile.registered_office),
            ("Business Address", ssm.business_address),
            ("Effective Date", f"{ssm.incorporation_date:%d %B %Y}"),
            ("Office Hours", "Monday to Friday, 9:00 a.m. to 5:00 p.m."),
        ),
        y,
    )
    c.showPage()

    _frame(c, ssm, 4, "Form 49", total_pages)
    y = draw_title(c, "FORM 49 - PARTICULARS OF DIRECTORS")
    director_rows = [
        (
            director.name,
            director.nric_or_passport or "N/A",
            "Malaysian",
            profile.business_address,
            f"{ssm.incorporation_date:%d/%m/%Y}",
        )
        for director in ssm.directors
    ]
    y = draw_table(
        c,
        ("Name", "IC No", "Nationality", "Address", "Appointed"),
        director_rows,
        (125, 105, 65, 135, 62),
        y,
        34,
        font_size=6.8,
    )
    y -= 38
    y = draw_section(c, "Directors:", y)
    c.setFont("Helvetica", 8.5)
    for index, director in enumerate(ssm.directors, start=1):
        c.drawString(
            LEFT + 6,
            y,
            f"{index}. {director.name} - NRIC: {director.nric_or_passport} - Role: {director.role}",
        )
        y -= 24
    c.showPage()

    _frame(c, ssm, 5, "Business Profile", total_pages)
    y = draw_title(c, "BUSINESS PROFILE SUMMARY", "Company information as at generation date")
    draw_key_values(
        c,
        (
            ("Company Name", ssm.company_name),
            ("Registration Number", ssm.registration_number),
            ("Company Status", "ACTIVE"),
            ("Business Nature", profile.business_nature),
            ("Authorised Capital", f"RM {ssm.paid_up_capital * Decimal('4'):,.2f}"),
            ("Paid-Up Capital", f"RM {ssm.paid_up_capital:,.2f}"),
            ("Date of Registration", f"{ssm.incorporation_date:%d %B %Y}"),
            ("Registered Office", profile.registered_office),
        ),
        y,
    )
    c.showPage()
    profile_sections = (
        "Company Charges",
        "Share Capital History",
        "Annual Return Extract",
        "Officer Appointment History",
        "Registered Address History",
    )
    for page_number in range(PAGE_COUNT + 1, total_pages + 1):
        section = profile_sections[(page_number - PAGE_COUNT - 1) % len(profile_sections)]
        _frame(c, ssm, page_number, section, total_pages)
        y = draw_title(c, section.upper(), "SSM business profile supporting extract")
        rows = [
            (
                f"Record {index:02d}",
                f"{ssm.incorporation_date:%d/%m/%Y}",
                "ACTIVE",
                ssm.registration_number,
            )
            for index in range(1, 12)
        ]
        draw_table(
            c,
            ("Record", "Effective Date", "Status", "Reference"),
            rows,
            (145, 105, 90, 152),
            y,
            28,
            font_size=8,
        )
        c.showPage()
    c.save()
    return output_path


def generate(
    cfg: SSMGeneratorConfig,
    out_dir: Path,
    coherent: CoherentFinancials | None = None,
) -> tuple[Path, Path]:
    profile = coherent or _profile_from_config(cfg)
    registration = build_ssm(cfg, profile)
    pdf_path = out_dir / "ssm_registration.pdf"
    render_pdf(registration, pdf_path, profile)
    json_path = pdf_path.with_suffix(".ground_truth.json")
    json_path.write_text(registration.model_dump_json(indent=2), encoding="utf-8")
    return pdf_path, json_path


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/samples")
    pdf, ground_truth = generate(SSMGeneratorConfig(), target)
    print(f"PDF:          {pdf}")
    print(f"Ground truth: {ground_truth}")
