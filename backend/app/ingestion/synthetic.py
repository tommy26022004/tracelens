"""Synthetic Malaysian bank statement generator.

Produces a PDF that resembles a Maybank-style monthly statement plus a
ground-truth JSON dump of the same statement. Used for:
- unit tests against the parser/extractor
- evaluation metrics (extraction accuracy vs. ground truth)

Layout choices mirror common Malaysian bank statement conventions:
- Header: bank name, address, statement period
- Account block: holder name, account number, statement number
- Transaction table: Date | Description | Debit | Credit | Balance
- Footer: totals + closing balance

Not a forgery tool — branding is generic ("Synthetic Bank Berhad").
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.ingestion.types import BankStatement, Transaction

MARGIN_X = 40
TOP_Y = 800
ROW_HEIGHT = 14
HEADER_FONT = ("Helvetica-Bold", 11)
BODY_FONT = ("Helvetica", 9)

COLUMNS = [
    ("Date", MARGIN_X, 60),
    ("Description", MARGIN_X + 65, 230),
    ("Debit (RM)", MARGIN_X + 305, 70),
    ("Credit (RM)", MARGIN_X + 385, 70),
    ("Balance (RM)", MARGIN_X + 470, 80),
]


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = 42
    period_start: date = date(2026, 1, 1)
    period_end: date = date(2026, 1, 31)
    opening_balance: Decimal = Decimal("125000.00")
    bank_name: str = "Synthetic Bank Berhad"
    account_holder: str = "ACME TRADING SDN BHD"
    account_number: str = "5141-2233-4455"
    n_transactions: int = 28


def _money(value: Decimal) -> str:
    return f"{value:,.2f}"


def _draw_header(c: canvas.Canvas, cfg: GeneratorConfig) -> float:
    c.setFont(*HEADER_FONT)
    c.drawString(MARGIN_X, TOP_Y, cfg.bank_name)
    c.setFont(*BODY_FONT)
    c.drawString(MARGIN_X, TOP_Y - 14, "Level 10, Menara Synthetic, Kuala Lumpur 50450")
    c.drawString(MARGIN_X, TOP_Y - 26, "Customer Service: 1-300-88-0000")

    c.setFont(*HEADER_FONT)
    c.drawString(MARGIN_X, TOP_Y - 58, "STATEMENT OF ACCOUNT")

    c.setFont(*BODY_FONT)
    c.drawString(MARGIN_X, TOP_Y - 76, f"Account Holder : {cfg.account_holder}")
    c.drawString(MARGIN_X, TOP_Y - 88, f"Account Number : {cfg.account_number}")
    period_str = (
        f"{cfg.period_start.strftime('%d %b %Y')} - {cfg.period_end.strftime('%d %b %Y')}"
    )
    c.drawString(MARGIN_X, TOP_Y - 100, f"Statement Period: {period_str}")
    return TOP_Y - 130


def _draw_table_header(c: canvas.Canvas, y: float) -> float:
    c.setFont(*HEADER_FONT)
    for label, x, _ in COLUMNS:
        c.drawString(x, y, label)
    c.line(MARGIN_X, y - 4, MARGIN_X + 560, y - 4)
    return y - 16


def _draw_row(c: canvas.Canvas, y: float, txn: Transaction) -> None:
    c.setFont(*BODY_FONT)
    cells = [
        txn.txn_date.strftime("%d/%m/%Y"),
        txn.description[:60],
        _money(txn.debit) if txn.debit is not None else "",
        _money(txn.credit) if txn.credit is not None else "",
        _money(txn.balance),
    ]
    for (_, x, _), value in zip(COLUMNS, cells, strict=True):
        c.drawString(x, y, value)


def _draw_footer(c: canvas.Canvas, y: float, stmt: BankStatement) -> None:
    c.line(MARGIN_X, y + 4, MARGIN_X + 560, y + 4)
    c.setFont(*HEADER_FONT)
    c.drawString(MARGIN_X, y - 8, f"Opening Balance : RM {_money(stmt.opening_balance)}")
    c.drawString(MARGIN_X, y - 22, f"Total Debits    : RM {_money(stmt.total_debits)}")
    c.drawString(MARGIN_X, y - 36, f"Total Credits   : RM {_money(stmt.total_credits)}")
    c.drawString(MARGIN_X, y - 50, f"Closing Balance : RM {_money(stmt.closing_balance)}")


def _synthesise_transactions(cfg: GeneratorConfig) -> list[Transaction]:
    rng = random.Random(cfg.seed)
    descriptions_credit = [
        "FPX TRANSFER FROM MAYBANK",
        "IBG INWARD - PEPPOL INVOICE PAYMENT",
        "CASH DEPOSIT MACHINE",
        "DUITNOW QR - CUSTOMER PAYMENT",
        "INTEREST PAYMENT",
    ]
    descriptions_debit = [
        "DUITNOW TRANSFER TO SUPPLIER",
        "PAYROLL EPF/SOCSO",
        "UTILITY BILL - TNB",
        "RENTAL PAYMENT",
        "GIRO - LHDN TAX",
        "ATM WITHDRAWAL",
    ]

    txns: list[Transaction] = []
    balance = cfg.opening_balance
    day_span = (cfg.period_end - cfg.period_start).days
    days = sorted(rng.sample(range(day_span + 1), min(cfg.n_transactions, day_span + 1)))

    for offset in days:
        txn_date = cfg.period_start + timedelta(days=offset)
        is_credit = rng.random() < 0.55
        amount = Decimal(f"{rng.uniform(120, 18000):.2f}")
        if is_credit:
            balance += amount
            txns.append(
                Transaction(
                    txn_date=txn_date,
                    description=rng.choice(descriptions_credit),
                    debit=None,
                    credit=amount,
                    balance=balance,
                    page=1,  # patched later when paginating
                )
            )
        else:
            balance -= amount
            txns.append(
                Transaction(
                    txn_date=txn_date,
                    description=rng.choice(descriptions_debit),
                    debit=amount,
                    credit=None,
                    balance=balance,
                    page=1,
                )
            )
    return txns


def build_statement(cfg: GeneratorConfig) -> BankStatement:
    txns = _synthesise_transactions(cfg)
    total_credits = sum((t.credit or Decimal(0) for t in txns), Decimal(0))
    total_debits = sum((t.debit or Decimal(0) for t in txns), Decimal(0))
    closing = cfg.opening_balance + total_credits - total_debits
    return BankStatement(
        bank_name=cfg.bank_name,
        account_holder=cfg.account_holder,
        account_number=cfg.account_number,
        statement_period_start=cfg.period_start,
        statement_period_end=cfg.period_end,
        opening_balance=cfg.opening_balance,
        closing_balance=closing,
        total_credits=total_credits,
        total_debits=total_debits,
        transactions=txns,
    )


def render_pdf(stmt: BankStatement, output_path: Path, cfg: GeneratorConfig) -> Path:
    """Render the statement to a PDF; paginates when rows exceed the page."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=A4)

    y = _draw_header(c, cfg)
    y = _draw_table_header(c, y)
    current_page = 1

    for idx, txn in enumerate(stmt.transactions):
        if y < 110:  # leave room for footer on the last page
            c.showPage()
            current_page += 1
            y = _draw_table_header(c, TOP_Y)
        # mutate the model's page so ground truth matches the rendered PDF
        stmt.transactions[idx] = txn.model_copy(update={"page": current_page})
        _draw_row(c, y, stmt.transactions[idx])
        y -= ROW_HEIGHT

    _draw_footer(c, max(y, 100), stmt)
    c.save()
    return output_path


def generate(cfg: GeneratorConfig, out_dir: Path) -> tuple[Path, Path]:
    """Generate one (pdf, ground_truth.json) pair. Returns both paths."""
    stmt = build_statement(cfg)
    pdf_path = out_dir / f"bank_statement_{cfg.period_start.isoformat()}.pdf"
    render_pdf(stmt, pdf_path, cfg)
    json_path = pdf_path.with_suffix(".ground_truth.json")
    json_path.write_text(stmt.model_dump_json(indent=2))
    return pdf_path, json_path


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/samples")
    pdf, gt = generate(GeneratorConfig(), target)
    print(f"PDF:          {pdf}")
    print(f"Ground truth: {gt}")
