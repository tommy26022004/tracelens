"""Synthetic audited-financials generator.

Produces a 2-page PDF resembling a simplified Malaysian SME audited
statement (Income Statement + Balance Sheet + Cash Flow summary) plus
a ground-truth JSON. Numbers are internally consistent so downstream
ratio calculations have a real signal to test against.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.ingestion.types import AuditedFinancials, FinancialPeriod

MARGIN_X = 50
TOP_Y = 800
ROW_GAP = 16
HEADER_FONT = ("Helvetica-Bold", 11)
LABEL_FONT = ("Helvetica", 10)
VALUE_FONT = ("Helvetica", 10)


@dataclass(frozen=True)
class FinancialsGeneratorConfig:
    seed: int = 42
    company_name: str = "ACME TRADING SDN BHD"
    auditor: str = "Synthetic Audit Partners PLT (SAMPLE)"
    financial_year_end: date = date(2025, 12, 31)
    base_revenue: Decimal = Decimal("1800000.00")
    revenue_growth_rate: float = 0.12  # YoY growth used for the prior period


def _money(value: Decimal) -> str:
    sign = "(" if value < 0 else ""
    end = ")" if value < 0 else ""
    return f"{sign}{abs(value):,.2f}{end}"


def _synthesise_period(
    rng: random.Random, revenue: Decimal, year_end: date
) -> FinancialPeriod:
    cost_ratio = rng.uniform(0.55, 0.65)
    opex_ratio = rng.uniform(0.18, 0.24)
    interest_ratio = rng.uniform(0.015, 0.03)
    tax_rate = 0.24  # SME corporate tax bracket approximation

    cost_of_sales = (revenue * Decimal(str(cost_ratio))).quantize(Decimal("0.01"))
    gross_profit = revenue - cost_of_sales
    operating_expenses = (revenue * Decimal(str(opex_ratio))).quantize(Decimal("0.01"))
    ebit = gross_profit - operating_expenses
    interest_expense = (revenue * Decimal(str(interest_ratio))).quantize(Decimal("0.01"))
    pre_tax = ebit - interest_expense
    tax = (pre_tax * Decimal(str(tax_rate))).quantize(Decimal("0.01")) if pre_tax > 0 else Decimal(0)
    net_profit = pre_tax - tax

    current_assets = (revenue * Decimal(str(rng.uniform(0.18, 0.28)))).quantize(Decimal("0.01"))
    non_current_assets = (revenue * Decimal(str(rng.uniform(0.30, 0.45)))).quantize(Decimal("0.01"))
    current_liabilities = (revenue * Decimal(str(rng.uniform(0.10, 0.18)))).quantize(Decimal("0.01"))
    non_current_liabilities = (revenue * Decimal(str(rng.uniform(0.10, 0.20)))).quantize(Decimal("0.01"))
    total_equity = (
        current_assets + non_current_assets - current_liabilities - non_current_liabilities
    )
    cash_from_operations = (ebit * Decimal(str(rng.uniform(0.7, 1.1)))).quantize(Decimal("0.01"))

    return FinancialPeriod(
        period_end=year_end,
        revenue=revenue,
        cost_of_sales=cost_of_sales,
        gross_profit=gross_profit,
        operating_expenses=operating_expenses,
        ebit=ebit,
        interest_expense=interest_expense,
        net_profit=net_profit,
        current_assets=current_assets,
        non_current_assets=non_current_assets,
        current_liabilities=current_liabilities,
        non_current_liabilities=non_current_liabilities,
        total_equity=total_equity,
        cash_from_operations=cash_from_operations,
    )


def build_financials(cfg: FinancialsGeneratorConfig) -> AuditedFinancials:
    rng = random.Random(cfg.seed)
    current = _synthesise_period(rng, cfg.base_revenue, cfg.financial_year_end)
    prior_year_end = date(
        cfg.financial_year_end.year - 1,
        cfg.financial_year_end.month,
        cfg.financial_year_end.day,
    )
    prior_revenue = (cfg.base_revenue / Decimal(str(1 + cfg.revenue_growth_rate))).quantize(
        Decimal("0.01")
    )
    prior = _synthesise_period(rng, prior_revenue, prior_year_end)
    return AuditedFinancials(
        company_name=cfg.company_name,
        auditor=cfg.auditor,
        financial_year_end=cfg.financial_year_end,
        periods=[current, prior],
        page_count=2,
    )


def _draw_header(c: canvas.Canvas, fin: AuditedFinancials) -> float:
    c.setFont(*HEADER_FONT)
    c.drawString(MARGIN_X, TOP_Y, fin.company_name)
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN_X, TOP_Y - 14, f"Audited by: {fin.auditor}")
    c.drawString(MARGIN_X, TOP_Y - 28, f"For the financial year ended {fin.financial_year_end:%d %B %Y}")
    c.line(MARGIN_X, TOP_Y - 36, MARGIN_X + 500, TOP_Y - 36)
    return TOP_Y - 60


def _draw_two_col_table(
    c: canvas.Canvas,
    y: float,
    title: str,
    rows: list[tuple[str, Decimal, Decimal]],
    period_labels: tuple[str, str],
) -> float:
    c.setFont(*HEADER_FONT)
    c.drawString(MARGIN_X, y, title)
    y -= ROW_GAP
    c.setFont(*LABEL_FONT)
    c.drawString(MARGIN_X + 280, y, period_labels[0])
    c.drawString(MARGIN_X + 390, y, period_labels[1])
    y -= 4
    c.line(MARGIN_X, y, MARGIN_X + 490, y)
    y -= ROW_GAP
    for label, current, prior in rows:
        c.setFont(*LABEL_FONT)
        c.drawString(MARGIN_X, y, label)
        c.setFont(*VALUE_FONT)
        c.drawRightString(MARGIN_X + 360, y, _money(current))
        c.drawRightString(MARGIN_X + 470, y, _money(prior))
        y -= ROW_GAP
    return y - 6


def render_pdf(fin: AuditedFinancials, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=A4)
    current, prior = fin.periods
    period_labels = (f"FY{current.period_end.year}", f"FY{prior.period_end.year}")

    # Page 1: Income statement + Cash flow
    y = _draw_header(c, fin)
    y = _draw_two_col_table(
        c,
        y,
        "INCOME STATEMENT",
        [
            ("Revenue", current.revenue, prior.revenue),
            ("Cost of Sales", -current.cost_of_sales, -prior.cost_of_sales),
            ("Gross Profit", current.gross_profit, prior.gross_profit),
            ("Operating Expenses", -current.operating_expenses, -prior.operating_expenses),
            ("EBIT", current.ebit, prior.ebit),
            ("Interest Expense", -current.interest_expense, -prior.interest_expense),
            ("Net Profit", current.net_profit, prior.net_profit),
        ],
        period_labels,
    )
    y = _draw_two_col_table(
        c,
        y - 10,
        "CASH FLOW SUMMARY",
        [("Cash from Operations", current.cash_from_operations, prior.cash_from_operations)],
        period_labels,
    )

    # Page 2: Balance sheet
    c.showPage()
    y = _draw_header(c, fin)
    _draw_two_col_table(
        c,
        y,
        "BALANCE SHEET",
        [
            ("Current Assets", current.current_assets, prior.current_assets),
            ("Non-Current Assets", current.non_current_assets, prior.non_current_assets),
            ("Total Assets", current.total_assets, prior.total_assets),
            ("Current Liabilities", current.current_liabilities, prior.current_liabilities),
            ("Non-Current Liabilities", current.non_current_liabilities, prior.non_current_liabilities),
            ("Total Liabilities", current.total_liabilities, prior.total_liabilities),
            ("Total Equity", current.total_equity, prior.total_equity),
        ],
        period_labels,
    )

    c.save()
    return output_path


def generate(cfg: FinancialsGeneratorConfig, out_dir: Path) -> tuple[Path, Path]:
    fin = build_financials(cfg)
    pdf_path = out_dir / f"audited_financials_{cfg.financial_year_end.year}.pdf"
    render_pdf(fin, pdf_path)
    json_path = pdf_path.with_suffix(".ground_truth.json")
    json_path.write_text(fin.model_dump_json(indent=2))
    return pdf_path, json_path


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/samples")
    pdf, gt = generate(FinancialsGeneratorConfig(), target)
    print(f"PDF:          {pdf}")
    print(f"Ground truth: {gt}")
