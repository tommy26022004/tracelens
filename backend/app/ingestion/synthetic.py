"""Multi-page synthetic Malaysian SME bank-statement generator."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.ingestion.coherent_financials import (
    CoherentFinancials,
    default_coherent_financials,
    money,
)
from app.ingestion.pdf_layout import LEFT, RIGHT, draw_page_frame, draw_section
from app.ingestion.types import BankStatement, Transaction

PAGE_WIDTH, PAGE_HEIGHT = A4
ROWS_PER_PAGE = 32


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = 42
    period_start: date = date(2026, 1, 1)
    period_end: date = date(2026, 1, 31)
    opening_balance: Decimal = Decimal("125000.00")
    bank_name: str = "MAYBANK BERHAD"
    account_holder: str = "ACME TRADING SDN BHD"
    account_number: str | None = None
    n_transactions: int = 28
    num_months: int = 6


def _month_start(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def _month_end(value: date) -> date:
    return date(value.year, value.month, calendar.monthrange(value.year, value.month)[1])


def _distribute(total: Decimal, count: int) -> list[Decimal]:
    if count <= 0:
        return []
    weights = [Decimal((index % 7) + 3) for index in range(count)]
    weight_total = sum(weights, Decimal(0))
    values = [money(total * weight / weight_total) for weight in weights]
    values[-1] = money(values[-1] + total - sum(values, Decimal(0)))
    return values


def _build_month_transactions(
    profile: CoherentFinancials,
    month_start: date,
    opening_balance: Decimal,
    count: int,
    month_index: int,
    package_days: int,
) -> list[Transaction]:
    month_end = _month_end(month_start)
    days = (month_end - month_start).days + 1
    package_credits = profile.bank_credits_for_days(package_days)
    monthly_credits = money(package_credits * Decimal(days) / Decimal(package_days))
    monthly_debits = money(monthly_credits * profile.bank_debit_ratio)

    credit_count = max(1, (count + 1) // 2)
    debit_count = max(0, count - credit_count)
    credits = iter(_distribute(monthly_credits, credit_count))
    debits = iter(_distribute(monthly_debits, debit_count))
    credit_descriptions = (
        "PAYMENT FM ALPHA RETAIL SDN BHD",
        "INTERBANK TRANSFER",
        "SALES COLLECTION",
        "CONTRA CREDIT",
        "PAYMENT FM METRO INDUSTRIES",
    )
    debit_descriptions = (
        "LHDN TAX PAYMENT",
        "KWSP CONTRIBUTION",
        "SOCSO PAYMENT",
        "SUPPLIER PAYMENT TO MEGA SUPPLIES",
        "UTILITIES - TNB",
        "TELEKOM MALAYSIA",
        "RENTAL PAYMENT",
        "BANK CHARGES",
    )

    transactions: list[Transaction] = []
    balance = opening_balance
    for index in range(count):
        transaction_date = month_start + timedelta(days=min((index * days) // count, days - 1))
        reference = f"MBB{transaction_date:%Y%m%d}{month_index * 1000 + index + 1:04d}"
        if index % 2 == 0:
            amount = next(credits)
            balance = money(balance + amount)
            transaction = Transaction(
                txn_date=transaction_date,
                description=credit_descriptions[(index // 2) % len(credit_descriptions)],
                reference_no=reference,
                credit=amount,
                balance=balance,
                page=1,
            )
        else:
            amount = next(debits)
            balance = money(balance - amount)
            transaction = Transaction(
                txn_date=transaction_date,
                description=debit_descriptions[(index // 2) % len(debit_descriptions)],
                reference_no=reference,
                debit=amount,
                balance=balance,
                page=1,
            )
        transactions.append(transaction)
    return transactions


def build_statement(
    cfg: GeneratorConfig,
    coherent: CoherentFinancials | None = None,
) -> BankStatement:
    profile = coherent or default_coherent_financials().with_changes(
        company_name=cfg.account_holder,
        bank_account_holder=cfg.account_holder,
        audited_company_name=cfg.account_holder,
        tax_company_name=cfg.account_holder,
        statement_start=cfg.period_start,
        opening_bank_balance=cfg.opening_balance,
    )
    transactions: list[Transaction] = []
    balance = profile.opening_bank_balance
    package_days = sum(
        (
            _month_end(_month_start(cfg.period_start, offset))
            - _month_start(cfg.period_start, offset)
        ).days
        + 1
        for offset in range(cfg.num_months)
    )
    for month_index in range(cfg.num_months):
        start = _month_start(cfg.period_start, month_index)
        month_transactions = _build_month_transactions(
            profile,
            start,
            balance,
            cfg.n_transactions,
            month_index + 1,
            package_days,
        )
        transactions.extend(month_transactions)
        if month_transactions:
            balance = month_transactions[-1].balance

    total_credits = sum((item.credit or Decimal(0) for item in transactions), Decimal(0))
    total_debits = sum((item.debit or Decimal(0) for item in transactions), Decimal(0))
    period_end = _month_end(_month_start(cfg.period_start, cfg.num_months - 1))
    return BankStatement(
        bank_name=cfg.bank_name,
        account_holder=profile.bank_account_holder,
        account_number=cfg.account_number or profile.account_number,
        statement_period_start=cfg.period_start,
        statement_period_end=period_end,
        opening_balance=profile.opening_bank_balance,
        closing_balance=balance,
        total_credits=money(total_credits),
        total_debits=money(total_debits),
        transactions=transactions,
    )


def _draw_summary_page(c: canvas.Canvas, stmt: BankStatement, page_count: int) -> None:
    draw_page_frame(c, stmt.account_holder, "BUSINESS CURRENT ACCOUNT", 1, page_count)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(LEFT, 742, stmt.bank_name)
    c.setFont("Helvetica", 8)
    c.drawString(LEFT, 725, f"Bank Name: {stmt.bank_name}")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(LEFT, 696, "ACCOUNT STATEMENT SUMMARY")
    rows = (
        ("Account Holder", stmt.account_holder),
        ("Account Number", stmt.account_number),
        (
            "Statement Period",
            f"{stmt.statement_period_start:%d %b %Y} - {stmt.statement_period_end:%d %b %Y}",
        ),
        ("Opening Balance", f"RM {stmt.opening_balance:,.2f}"),
        ("Closing Balance", f"RM {stmt.closing_balance:,.2f}"),
        ("Total Credits", f"RM {stmt.total_credits:,.2f}"),
        ("Total Debits", f"RM {stmt.total_debits:,.2f}"),
    )
    y = 650
    for label, value in rows:
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(LEFT, y, label)
        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica", 10)
        c.drawString(210, y, value)
        c.setStrokeColor(colors.HexColor("#CBD5E1"))
        c.line(LEFT, y - 8, RIGHT, y - 8)
        y -= 42
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#64748B"))
    c.drawString(LEFT, 105, "Synthetic statement generated for academic testing only.")
    c.showPage()


def _draw_transaction_page(
    c: canvas.Canvas,
    stmt: BankStatement,
    month_transactions: list[Transaction],
    all_month_transactions: list[Transaction],
    page_number: int,
    page_count: int,
    month_label: str,
    chunk_index: int,
    chunk_count: int,
) -> None:
    draw_page_frame(c, stmt.account_holder, "BANK STATEMENT", page_number, page_count)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 14)
    continuation = f" (Part {chunk_index + 1} of {chunk_count})" if chunk_count > 1 else ""
    c.drawString(LEFT, 748, f"Bank Statement - {month_label}{continuation}")
    c.setFont("Helvetica", 8)
    c.drawString(LEFT, 729, f"Account Number: {stmt.account_number}")

    headers = ("Date", "Description", "Reference No", "Debit (RM)", "Credit (RM)", "Balance (RM)")
    positions = (LEFT, 88, 270, 383, 443, 504, RIGHT)
    y = 700
    c.setFillColor(colors.HexColor("#D9EAF7"))
    c.rect(LEFT, y - 18, RIGHT - LEFT, 18, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 7)
    for index, header in enumerate(headers):
        c.drawString(positions[index] + 2, y - 12, header)
    y -= 18
    c.setFont("Helvetica", 6.7)
    for transaction in month_transactions:
        y -= 18
        c.setStrokeColor(colors.HexColor("#CBD5E1"))
        c.rect(LEFT, y, RIGHT - LEFT, 18, fill=0, stroke=1)
        values = (
            transaction.txn_date.strftime("%d/%m/%Y"),
            transaction.description,
            transaction.reference_no or "",
            f"{transaction.debit:,.2f}" if transaction.debit is not None else "",
            f"{transaction.credit:,.2f}" if transaction.credit is not None else "",
            f"{transaction.balance:,.2f}",
        )
        for index, value in enumerate(values):
            if index >= 3:
                c.drawRightString(positions[index + 1] - 3, y + 6, value)
            else:
                c.drawString(positions[index] + 2, y + 6, value[:45])

    if chunk_index == chunk_count - 1:
        monthly_credits = sum(
            (item.credit or Decimal(0) for item in all_month_transactions), Decimal(0)
        )
        monthly_debits = sum(
            (item.debit or Decimal(0) for item in all_month_transactions), Decimal(0)
        )
        opening = (
            all_month_transactions[0].balance
            - (all_month_transactions[0].credit or Decimal(0))
            + (all_month_transactions[0].debit or Decimal(0))
        )
        closing = all_month_transactions[-1].balance
        y = min(y - 28, 102)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(LEFT, y, f"Opening Balance: RM {opening:,.2f}")
        c.drawString(LEFT + 165, y, f"Total Credits: RM {monthly_credits:,.2f}")
        c.drawString(LEFT + 330, y, f"Total Debits: RM {monthly_debits:,.2f}")
        c.drawRightString(RIGHT, y - 16, f"Closing Balance: RM {closing:,.2f}")
    c.showPage()


def _draw_reconciliation_page(c: canvas.Canvas, stmt: BankStatement, page_count: int) -> None:
    draw_page_frame(c, stmt.account_holder, "ACCOUNT RECONCILIATION", page_count, page_count)
    y = draw_section(c, "STATEMENT TOTALS", 742)
    c.setFont("Helvetica-Bold", 10)
    lines = (
        f"Opening Balance : RM {stmt.opening_balance:,.2f}",
        f"Total Debits    : RM {stmt.total_debits:,.2f}",
        f"Total Credits   : RM {stmt.total_credits:,.2f}",
        f"Closing Balance : RM {stmt.closing_balance:,.2f}",
    )
    for line in lines:
        c.drawString(LEFT + 8, y, line)
        y -= 25
    y -= 20
    y = draw_section(c, "TRANSACTION REFERENCE GUIDE", y)
    c.setFont("Helvetica", 9)
    c.drawString(LEFT + 8, y, "MBBYYYYMMDDNNNN identifies the posting date and sequence number.")
    c.drawString(
        LEFT + 8,
        y - 22,
        "All balances are calculated after each transaction and carried forward monthly.",
    )
    c.showPage()


def render_pdf(stmt: BankStatement, output_path: Path, cfg: GeneratorConfig) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    grouped: list[list[Transaction]] = []
    for month_index in range(cfg.num_months):
        month = _month_start(stmt.statement_period_start, month_index)
        grouped.append(
            [
                item
                for item in stmt.transactions
                if item.txn_date.year == month.year and item.txn_date.month == month.month
            ]
        )

    chunks = [
        (
            month_index,
            items[start : start + ROWS_PER_PAGE],
            start // ROWS_PER_PAGE,
            max(1, (len(items) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE),
        )
        for month_index, items in enumerate(grouped)
        for start in range(0, max(len(items), 1), ROWS_PER_PAGE)
    ]
    page_count = 2 + len(chunks)
    c = canvas.Canvas(str(output_path), pagesize=A4)
    _draw_summary_page(c, stmt, page_count)

    page_number = 2
    transaction_index = 0
    for month_index, chunk, chunk_index, chunk_count in chunks:
        for item_index, transaction in enumerate(chunk):
            stmt.transactions[transaction_index + item_index] = transaction.model_copy(
                update={"page": page_number}
            )
        transaction_index += len(chunk)
        month = _month_start(stmt.statement_period_start, month_index)
        _draw_transaction_page(
            c,
            stmt,
            chunk,
            grouped[month_index],
            page_number,
            page_count,
            month.strftime("%B %Y"),
            chunk_index,
            chunk_count,
        )
        page_number += 1
    _draw_reconciliation_page(c, stmt, page_count)
    c.save()
    return output_path


def generate(
    cfg: GeneratorConfig,
    out_dir: Path,
    coherent: CoherentFinancials | None = None,
) -> tuple[Path, Path]:
    stmt = build_statement(cfg, coherent)
    pdf_path = out_dir / "bank_statement.pdf"
    render_pdf(stmt, pdf_path, cfg)
    json_path = pdf_path.with_suffix(".ground_truth.json")
    json_path.write_text(stmt.model_dump_json(indent=2), encoding="utf-8")
    return pdf_path, json_path


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/samples")
    pdf, ground_truth = generate(GeneratorConfig(), target)
    print(f"PDF:          {pdf}")
    print(f"Ground truth: {ground_truth}")
