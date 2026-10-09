"""Seven-page synthetic audited-financial-statements generator."""

from __future__ import annotations

from dataclasses import dataclass
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
    draw_page_frame,
    draw_section,
    draw_table,
    draw_title,
    format_money,
)
from app.ingestion.types import AuditedFinancials

PAGE_COUNT = 7


@dataclass(frozen=True)
class FinancialsGeneratorConfig:
    seed: int = 42
    company_name: str = "ACME TRADING SDN BHD"
    registration_number: str = "202401000123 (1500123-X)"
    auditor: str = "Synthetic Audit Partners PLT"
    auditor_number: str = "AF 009999"
    financial_year_end: date = date(2025, 12, 31)
    base_revenue: Decimal = Decimal("1800000.00")
    revenue_growth_rate: float = 0.12


def _profile_from_config(cfg: FinancialsGeneratorConfig) -> CoherentFinancials:
    prior_revenue = cfg.base_revenue / Decimal(str(1 + cfg.revenue_growth_rate))
    scale = cfg.base_revenue / Decimal("1800000.00")
    base = default_coherent_financials()
    return base.with_changes(
        company_name=cfg.company_name,
        bank_account_holder=cfg.company_name,
        audited_company_name=cfg.company_name,
        tax_company_name=cfg.company_name,
        registration_number=cfg.registration_number,
        auditor=cfg.auditor,
        auditor_number=cfg.auditor_number,
        financial_year_end=cfg.financial_year_end,
        revenue=cfg.base_revenue,
        prior_revenue=prior_revenue,
        cost_of_sales=base.cost_of_sales * scale,
        salaries=base.salaries * scale,
        rental_expense=base.rental_expense * scale,
        depreciation=base.depreciation * scale,
        administrative_expenses=base.administrative_expenses * scale,
        finance_costs=base.finance_costs * scale,
        tax_expense=base.tax_expense * scale,
        ppe=base.ppe * scale,
        intangible_assets=base.intangible_assets * scale,
        trade_receivables=base.trade_receivables * scale,
        cash_and_bank=base.cash_and_bank * scale,
        inventories=base.inventories * scale,
        trade_payables=base.trade_payables * scale,
        short_term_borrowings=base.short_term_borrowings * scale,
        tax_payable_balance=base.tax_payable_balance * scale,
        long_term_borrowings=base.long_term_borrowings * scale,
        paid_up_capital=base.paid_up_capital * scale,
        retained_earnings=base.retained_earnings * scale,
        cash_from_operations=base.cash_from_operations * scale,
    )


def build_financials(
    cfg: FinancialsGeneratorConfig,
    coherent: CoherentFinancials | None = None,
) -> AuditedFinancials:
    profile = coherent or _profile_from_config(cfg)
    return AuditedFinancials(
        company_name=profile.audited_company_name,
        auditor=f"{profile.auditor} ({profile.auditor_number})",
        financial_year_end=profile.financial_year_end,
        periods=[profile.current_period(), profile.prior_period()],
        page_count=PAGE_COUNT,
    )


def _frame(
    c: canvas.Canvas,
    fin: AuditedFinancials,
    page: int,
    title: str,
    page_count: int,
) -> None:
    draw_page_frame(c, fin.company_name, "AUDITED FINANCIAL STATEMENTS", page, page_count)
    c.setFillColor(colors.HexColor("#334155"))
    c.setFont("Helvetica", 8)
    c.drawRightString(RIGHT, 49, title)


def _end(c: canvas.Canvas) -> None:
    c.showPage()


def _financial_rows(rows: list[tuple[str, Decimal, Decimal]]) -> list[tuple[str, str, str]]:
    return [(label, format_money(current), format_money(prior)) for label, current, prior in rows]


def render_pdf(
    fin: AuditedFinancials,
    output_path: Path,
    profile: CoherentFinancials | None = None,
    supplemental_pages: int = 0,
) -> Path:
    profile = profile or default_coherent_financials().with_changes(
        audited_company_name=fin.company_name,
        company_name=fin.company_name,
        financial_year_end=fin.financial_year_end,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=A4)
    current, prior = fin.periods
    year_labels = (f"FY{current.period_end.year}", f"FY{prior.period_end.year}")
    total_pages = PAGE_COUNT + supplemental_pages

    _frame(c, fin, 1, "Cover", total_pages)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(A4[0] / 2, 690, fin.company_name)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(A4[0] / 2, 620, "AUDITED FINANCIAL STATEMENTS")
    c.setFont("Helvetica", 11)
    c.drawCentredString(
        A4[0] / 2,
        578,
        f"For the financial year ended {fin.financial_year_end:%d %B %Y}",
    )
    c.drawCentredString(A4[0] / 2, 535, f"Registration No.: {profile.registration_number}")
    c.drawCentredString(A4[0] / 2, 466, f"Audited by: {fin.auditor}")
    c.drawCentredString(A4[0] / 2, 444, "Chartered Accountants")
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(A4[0] / 2, 115, "Synthetic document for academic evaluation")
    _end(c)

    _frame(c, fin, 2, "Directors' Report", total_pages)
    y = draw_title(c, "DIRECTORS' REPORT", "For the year under review")
    paragraphs = (
        "The directors present their report together with the audited financial statements",
        "of the Company for the financial year ended 31 December 2025.",
        f"Principal activities: {profile.business_nature}.",
        "There were no significant changes in the nature of these activities during the year.",
        f"Net profit for the year: RM {current.net_profit:,.2f}",
    )
    c.setFont("Helvetica", 10)
    for paragraph in paragraphs:
        c.drawString(LEFT, y, paragraph)
        y -= 23
    y -= 20
    y = draw_section(c, "DIRECTORS IN OFFICE", y)
    for director in profile.directors:
        c.drawString(LEFT + 8, y, f"{director.name} - {director.role or 'Director'}")
        y -= 22
    y -= 25
    c.drawString(
        LEFT, y, "Signed on behalf of the Board in accordance with a resolution of the directors."
    )
    c.line(LEFT, y - 75, LEFT + 190, y - 75)
    c.drawString(LEFT, y - 90, profile.directors[0].name)
    _end(c)

    _frame(c, fin, 3, "Independent Auditors' Report", total_pages)
    y = draw_title(c, "INDEPENDENT AUDITORS' REPORT", f"To the Members of {fin.company_name}")
    y = draw_section(c, "OPINION", y)
    text_lines = (
        "We have audited the accompanying financial statements of the Company, which comprise",
        "the statement of financial position, statement of profit or loss, statement of cash flows",
        "and notes to the financial statements, including significant accounting policies.",
        "In our opinion, the financial statements give a true and fair view of the financial",
        "position and financial performance of the Company in accordance with applicable",
        "Malaysian Financial Reporting Standards and the Companies Act 2016.",
    )
    c.setFont("Helvetica", 9.5)
    for line in text_lines:
        c.drawString(LEFT, y, line)
        y -= 20
    y -= 15
    y = draw_section(c, "BASIS FOR OPINION", y)
    for line in (
        "We conducted our audit in accordance with approved standards on auditing in Malaysia.",
        "We are independent of the Company and believe the audit evidence obtained is sufficient.",
    ):
        c.drawString(LEFT, y, line)
        y -= 20
    y -= 50
    c.setFont("Helvetica-Bold", 10)
    c.drawString(LEFT, y, fin.auditor)
    c.setFont("Helvetica", 9)
    c.drawString(LEFT, y - 20, "Chartered Accountants")
    c.drawString(LEFT, y - 40, f"Kuala Lumpur, {profile.audit_date:%d %B %Y}")
    _end(c)

    _frame(c, fin, 4, "Income Statement", total_pages)
    y = draw_title(c, "INCOME STATEMENT", "Amounts in Ringgit Malaysia")
    rows = _financial_rows(
        [
            ("Revenue", current.revenue, prior.revenue),
            ("Cost of Sales", -current.cost_of_sales, -prior.cost_of_sales),
            ("Gross Profit", current.gross_profit, prior.gross_profit),
            (
                "Salaries and Wages",
                -profile.salaries,
                -(profile.salaries * prior.revenue / current.revenue),
            ),
            (
                "Rental Expenses",
                -profile.rental_expense,
                -(profile.rental_expense * prior.revenue / current.revenue),
            ),
            (
                "Depreciation",
                -profile.depreciation,
                -(profile.depreciation * prior.revenue / current.revenue),
            ),
            (
                "Administrative Expenses",
                -profile.administrative_expenses,
                -(profile.administrative_expenses * prior.revenue / current.revenue),
            ),
            ("Operating Expenses", -current.operating_expenses, -prior.operating_expenses),
            ("EBIT", current.ebit, prior.ebit),
            ("Interest Expense", -current.interest_expense, -prior.interest_expense),
            ("Profit Before Tax", profile.profit_before_tax, prior.ebit - prior.interest_expense),
            (
                "Tax Expense",
                -profile.tax_expense,
                -(profile.tax_expense * prior.revenue / current.revenue),
            ),
            ("Net Profit", current.net_profit, prior.net_profit),
        ]
    )
    draw_table(c, ("", *year_labels), rows, (276, 108, 108), y, 26, ("left", "right", "right"), 8.5)
    _end(c)

    _frame(c, fin, 5, "Balance Sheet", total_pages)
    y = draw_title(c, "BALANCE SHEET", "Amounts in Ringgit Malaysia")
    scale = prior.revenue / current.revenue
    rows = _financial_rows(
        [
            ("Property, Plant and Equipment", profile.ppe, profile.ppe * scale),
            ("Intangible Assets", profile.intangible_assets, profile.intangible_assets * scale),
            ("Non-Current Assets", current.non_current_assets, prior.non_current_assets),
            ("Trade Receivables", profile.trade_receivables, profile.trade_receivables * scale),
            ("Cash and Bank Balances", profile.cash_and_bank, profile.cash_and_bank * scale),
            ("Inventories", profile.inventories, profile.inventories * scale),
            ("Current Assets", current.current_assets, prior.current_assets),
            ("Trade Payables", profile.trade_payables, profile.trade_payables * scale),
            (
                "Short-Term Borrowings",
                profile.short_term_borrowings,
                profile.short_term_borrowings * scale,
            ),
            ("Tax Payable", profile.tax_payable_balance, profile.tax_payable_balance * scale),
            ("Current Liabilities", current.current_liabilities, prior.current_liabilities),
            (
                "Long-Term Borrowings",
                profile.long_term_borrowings,
                profile.long_term_borrowings * scale,
            ),
            (
                "Non-Current Liabilities",
                current.non_current_liabilities,
                prior.non_current_liabilities,
            ),
            ("Paid-Up Capital", profile.paid_up_capital, profile.paid_up_capital * scale),
            ("Retained Earnings", profile.retained_earnings, profile.retained_earnings * scale),
            ("Total Equity", current.total_equity, prior.total_equity),
        ]
    )
    draw_table(c, ("", *year_labels), rows, (276, 108, 108), y, 23, ("left", "right", "right"), 8)
    _end(c)

    _frame(c, fin, 6, "Cash Flow Statement", total_pages)
    y = draw_title(c, "CASH FLOW STATEMENT", "Amounts in Ringgit Malaysia")
    rows = _financial_rows(
        [
            ("Cash from Operations", current.cash_from_operations, prior.cash_from_operations),
            (
                "Cash Used in Investing Activities",
                profile.cash_from_investing,
                profile.cash_from_investing * scale,
            ),
            (
                "Cash Used in Financing Activities",
                profile.cash_from_financing,
                profile.cash_from_financing * scale,
            ),
            (
                "Net Change in Cash",
                profile.cash_from_operations
                + profile.cash_from_investing
                + profile.cash_from_financing,
                prior.cash_from_operations
                + profile.cash_from_investing * scale
                + profile.cash_from_financing * scale,
            ),
            (
                "Cash at Beginning of Year",
                profile.cash_and_bank
                - profile.cash_from_operations
                - profile.cash_from_investing
                - profile.cash_from_financing,
                profile.cash_and_bank * scale
                - prior.cash_from_operations
                - profile.cash_from_investing * scale
                - profile.cash_from_financing * scale,
            ),
            ("Cash at End of Year", profile.cash_and_bank, profile.cash_and_bank * scale),
        ]
    )
    draw_table(c, ("", *year_labels), rows, (276, 108, 108), y, 28, ("left", "right", "right"), 8.5)
    _end(c)

    _frame(c, fin, 7, "Notes to the Financial Statements", total_pages)
    y = draw_title(c, "NOTES TO THE FINANCIAL STATEMENTS")
    notes = (
        ("NOTE 1 - PRINCIPAL ACTIVITIES", profile.business_nature),
        (
            "NOTE 2 - SIGNIFICANT ACCOUNTING POLICIES",
            "The statements are prepared on the historical cost basis and going-concern assumption.",
        ),
        (
            "NOTE 3 - REVENUE BREAKDOWN",
            f"Product sales RM {profile.revenue * Decimal('0.82'):,.2f}; service and delivery income RM {profile.revenue * Decimal('0.18'):,.2f}.",
        ),
        (
            "NOTE 4 - PROPERTY, PLANT AND EQUIPMENT",
            f"Opening carrying amount RM {profile.ppe + profile.depreciation:,.2f}; depreciation RM {profile.depreciation:,.2f}; closing carrying amount RM {profile.ppe:,.2f}.",
        ),
    )
    for heading, body in notes:
        y = draw_section(c, heading, y)
        c.setFont("Helvetica", 9)
        c.drawString(LEFT + 7, y, body)
        y -= 48
    _end(c)

    note_topics = (
        "Corporate Information",
        "Basis of Preparation",
        "Revenue Recognition",
        "Trade Receivables Ageing",
        "Inventory Valuation",
        "Property, Plant and Equipment",
        "Borrowings and Security",
        "Related Party Transactions",
        "Taxation Reconciliation",
        "Financial Risk Management",
        "Commitments and Contingencies",
    )
    for page_number in range(PAGE_COUNT + 1, total_pages + 1):
        topic = note_topics[(page_number - PAGE_COUNT - 1) % len(note_topics)]
        _frame(c, fin, page_number, f"Notes - {topic}", total_pages)
        y = draw_title(c, f"NOTE {page_number - 3} - {topic.upper()}")
        c.setFont("Helvetica", 9)
        for line_number in range(1, 13):
            c.drawString(
                LEFT,
                y,
                f"{line_number}. Supporting disclosure for {topic.lower()} and comparative FY{prior.period_end.year} information.",
            )
            y -= 22
        y -= 15
        draw_table(
            c,
            ("Disclosure item", year_labels[0], year_labels[1]),
            [
                (
                    f"{topic} item {index}",
                    format_money(current.revenue / Decimal(index + 8)),
                    format_money(prior.revenue / Decimal(index + 8)),
                )
                for index in range(1, 7)
            ],
            (276, 108, 108),
            y,
            24,
            ("left", "right", "right"),
            8,
        )
        _end(c)

    c.save()
    return output_path


def generate(
    cfg: FinancialsGeneratorConfig,
    out_dir: Path,
    coherent: CoherentFinancials | None = None,
) -> tuple[Path, Path]:
    profile = coherent or _profile_from_config(cfg)
    financials = build_financials(cfg, profile)
    pdf_path = out_dir / "audited_financials.pdf"
    render_pdf(financials, pdf_path, profile)
    json_path = pdf_path.with_suffix(".ground_truth.json")
    json_path.write_text(financials.model_dump_json(indent=2), encoding="utf-8")
    return pdf_path, json_path


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/samples")
    pdf, ground_truth = generate(FinancialsGeneratorConfig(), target)
    print(f"PDF:          {pdf}")
    print(f"Ground truth: {ground_truth}")
