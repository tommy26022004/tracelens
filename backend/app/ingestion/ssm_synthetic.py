"""Synthetic SSM registration form generator.

Produces a PDF resembling a Malaysian SSM Form 9 (registration of a
private limited company) plus a ground-truth JSON dump. Used for unit
tests and extraction-accuracy evaluation.

Not a forgery tool — uses a generic registrar branding ("Synthetic
SSM Office") and explicit "SAMPLE" watermark.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.ingestion.types import Director, SSMRegistration

MARGIN_X = 50
TOP_Y = 800
ROW_GAP = 18
HEADER_FONT = ("Helvetica-Bold", 12)
LABEL_FONT = ("Helvetica-Bold", 10)
VALUE_FONT = ("Helvetica", 10)


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


def _draw_form_header(c: canvas.Canvas) -> float:
    c.setFont(*HEADER_FONT)
    c.drawString(MARGIN_X, TOP_Y, "SURUHANJAYA SYARIKAT MALAYSIA")
    c.drawString(MARGIN_X, TOP_Y - 14, "(Synthetic SSM Office - SAMPLE)")
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN_X, TOP_Y - 28, "FORM 9 - CERTIFICATE OF INCORPORATION")
    c.line(MARGIN_X, TOP_Y - 36, MARGIN_X + 480, TOP_Y - 36)
    return TOP_Y - 60


def _draw_field(c: canvas.Canvas, y: float, label: str, value: str) -> float:
    c.setFont(*LABEL_FONT)
    c.drawString(MARGIN_X, y, f"{label}:")
    c.setFont(*VALUE_FONT)
    c.drawString(MARGIN_X + 180, y, value)
    return y - ROW_GAP


def _synthesise_directors(cfg: SSMGeneratorConfig) -> list[Director]:
    rng = random.Random(cfg.seed)
    chosen = rng.sample(cfg.director_pool, min(cfg.director_count, len(cfg.director_pool)))
    roles = ["Director", "Director", "Director / Company Secretary"]
    return [
        Director(name=name, nric_or_passport=nric, role=rng.choice(roles))
        for name, nric in chosen
    ]


def build_ssm(cfg: SSMGeneratorConfig) -> SSMRegistration:
    return SSMRegistration(
        company_name=cfg.company_name,
        registration_number=cfg.registration_number,
        incorporation_date=cfg.incorporation_date,
        company_type=cfg.company_type,
        business_address=cfg.business_address,
        paid_up_capital=cfg.paid_up_capital,
        directors=_synthesise_directors(cfg),
        page_count=1,
    )


def render_pdf(ssm: SSMRegistration, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=A4)
    y = _draw_form_header(c)

    y = _draw_field(c, y, "Company Name", ssm.company_name)
    y = _draw_field(c, y, "Registration Number", ssm.registration_number)
    y = _draw_field(c, y, "Date of Incorporation", ssm.incorporation_date.strftime("%d %B %Y"))
    y = _draw_field(c, y, "Company Type", ssm.company_type)
    y = _draw_field(c, y, "Business Address", ssm.business_address)
    y = _draw_field(c, y, "Paid-Up Capital", f"RM {ssm.paid_up_capital:,.2f}")

    y -= 10
    c.setFont(*HEADER_FONT)
    c.drawString(MARGIN_X, y, "Directors:")
    y -= ROW_GAP
    for idx, director in enumerate(ssm.directors, start=1):
        line = f"{idx}. {director.name}  -  NRIC: {director.nric_or_passport or '-'}  -  Role: {director.role or '-'}"
        c.setFont(*VALUE_FONT)
        c.drawString(MARGIN_X + 10, y, line)
        y -= ROW_GAP

    c.save()
    return output_path


def generate(cfg: SSMGeneratorConfig, out_dir: Path) -> tuple[Path, Path]:
    """Generate one (pdf, ground_truth.json) pair."""
    ssm = build_ssm(cfg)
    pdf_path = out_dir / f"ssm_{cfg.registration_number.split(' ')[0]}.pdf"
    render_pdf(ssm, pdf_path)
    json_path = pdf_path.with_suffix(".ground_truth.json")
    json_path.write_text(ssm.model_dump_json(indent=2))
    return pdf_path, json_path


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/samples")
    pdf, gt = generate(SSMGeneratorConfig(), target)
    print(f"PDF:          {pdf}")
    print(f"Ground truth: {gt}")
