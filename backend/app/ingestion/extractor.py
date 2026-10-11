"""Bank-statement extractor.

Turns the loose `TextSpan`s produced by `parser.parse_pdf` into a
structured `BankStatement` (account metadata, period, transactions,
totals).

This first pass is heuristic — it locates spans by row (y-coordinate)
and by column boundaries declared by the generator. A second pass using
LLM-assisted extraction is planned in Phase 3 to handle real Malaysian
banks whose column positions vary. Keeping this layer deterministic now
gives us a measurable baseline against the synthetic ground truth.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.ingestion.parser import ParsedPage, TextSpan
from app.ingestion.provenance import labelled_sources, source_location
from app.ingestion.types import BankStatement, Transaction

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
MONEY_RE = re.compile(r"^-?\d{1,3}(?:,\d{3})*\.\d{2}$")
PERIOD_RE = re.compile(r"Statement Period\s*:?\s*(\d{2} \w{3} \d{4})\s*-\s*(\d{2} \w{3} \d{4})")
ROW_TOLERANCE: float = 3.0  # spans within this many points share a row


@dataclass(frozen=True)
class TransactionColumns:
    date: float
    description: float
    debit: float
    credit: float
    balance: float
    reference: float | None = None


def _span_midpoint(span: TextSpan) -> float:
    return (span.bbox[0] + span.bbox[2]) / 2


def _normalise_header(value: str) -> str:
    return re.sub(r"[^a-z]+", " ", value.lower()).strip()


def _header_position(span: TextSpan, names: tuple[str, ...]) -> float | None:
    text = _normalise_header(span.text)
    for name in sorted(names, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(name)}\b", text)
        if match is None:
            continue
        width = span.bbox[2] - span.bbox[0]
        centre_ratio = ((match.start() + match.end()) / 2) / max(len(text), 1)
        return span.bbox[0] + width * centre_ratio
    return None


def _detect_transaction_columns(rows: list[list[TextSpan]]) -> TransactionColumns:
    """Infer transaction column centres from the table header text."""
    aliases = {
        "date": ("date", "transaction date"),
        "description": ("description", "details", "transaction details"),
        "reference": ("reference", "reference no", "ref", "ref no"),
        "debit": ("debit", "debit rm", "withdrawal", "money out"),
        "credit": ("credit", "credit rm", "deposit", "money in"),
        "balance": ("balance", "balance rm", "running balance"),
    }
    required = {"date", "description", "debit", "credit", "balance"}
    best: dict[str, float] = {}
    for row in rows:
        candidates: dict[str, float] = {}
        for span in row:
            for key, names in aliases.items():
                position = _header_position(span, names)
                if position is not None:
                    candidates[key] = position
        if len(required & candidates.keys()) > len(required & best.keys()):
            best = candidates
        if required <= candidates.keys():
            best = candidates
            break
    if not required <= best.keys():
        missing = ", ".join(sorted(required - best.keys()))
        raise ValueError(f"Could not detect transaction columns from header; missing: {missing}")
    return TransactionColumns(
        date=best["date"],
        description=best["description"],
        reference=best.get("reference"),
        debit=best["debit"],
        credit=best["credit"],
        balance=best["balance"],
    )


def _to_decimal(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def _parse_date_cell(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


def _parse_period(value: str) -> date:
    return datetime.strptime(value, "%d %b %Y").date()


def _group_into_rows(spans: list[TextSpan]) -> list[list[TextSpan]]:
    """Cluster spans whose y-midpoint is within ROW_TOLERANCE of each other."""
    by_y: dict[int, list[TextSpan]] = defaultdict(list)
    for span in spans:
        y_mid = (span.bbox[1] + span.bbox[3]) / 2
        # bucket by quantised y; collisions get merged below
        bucket = round(y_mid / ROW_TOLERANCE) * ROW_TOLERANCE
        by_y[int(bucket)].append(span)
    rows = [sorted(group, key=lambda s: s.bbox[0]) for _, group in sorted(by_y.items())]
    return rows


def _find_label(rows: list[list[TextSpan]], prefix: str) -> str | None:
    for row in rows:
        text = " ".join(s.text for s in row)
        if text.startswith(prefix):
            return text[len(prefix) :].lstrip(" :").strip()
    return None


def _find_money_after(rows: list[list[TextSpan]], label: str) -> Decimal | None:
    pattern = re.compile(rf"^{re.escape(label)}\s*:\s*RM\s*([\d,]+\.\d{{2}})")
    for row in rows:
        text = " ".join(s.text for s in row)
        match = pattern.search(text)
        if match:
            return _to_decimal(match.group(1))
    return None


def _row_is_transaction(row: list[TextSpan]) -> bool:
    return bool(row) and DATE_RE.match(row[0].text) is not None


def _parse_transaction_row(
    row: list[TextSpan], page: int, columns: TransactionColumns
) -> Transaction:
    """Map transaction cells to the nearest detected header column."""
    date_span = row[0]
    money_spans = [s for s in row[1:] if MONEY_RE.match(s.text)]
    text_spans = [s for s in row[1:] if not MONEY_RE.match(s.text)]
    text_columns = {"description": columns.description}
    if columns.reference is not None:
        text_columns["reference"] = columns.reference
    assigned_text: dict[str, list[TextSpan]] = {"description": [], "reference": []}
    for span in text_spans:
        key = min(text_columns, key=lambda name: abs(_span_midpoint(span) - text_columns[name]))
        assigned_text[key].append(span)
    description_spans = assigned_text["description"]
    reference_spans = assigned_text["reference"]
    description = " ".join(s.text for s in description_spans).strip()
    reference_no = " ".join(s.text for s in reference_spans).strip() or None

    if not money_spans:
        raise ValueError(f"Transaction row missing money cells: {row!r}")
    money_columns = {
        "debit": columns.debit,
        "credit": columns.credit,
        "balance": columns.balance,
    }
    assigned_money: dict[str, Decimal | None] = {name: None for name in money_columns}
    for span in money_spans:
        key = min(money_columns, key=lambda name: abs(_span_midpoint(span) - money_columns[name]))
        if assigned_money[key] is not None:
            raise ValueError(f"Transaction row has multiple values in {key} column: {row!r}")
        assigned_money[key] = _to_decimal(span.text)
    balance = assigned_money["balance"]
    if balance is None:
        raise ValueError(f"Transaction row missing balance cell: {row!r}")

    return Transaction(
        txn_date=_parse_date_cell(date_span.text),
        description=description,
        reference_no=reference_no,
        debit=assigned_money["debit"],
        credit=assigned_money["credit"],
        balance=balance,
        page=page,
        source=source_location(row),
    )


def extract_bank_statement(pages: list[ParsedPage]) -> BankStatement:
    """Return a `BankStatement` built from parsed pages.

    Raises `ValueError` if mandatory header fields cannot be located. This is
    intentional — a missing header means the document is not the format we
    claim to support, which the caller should surface to the loan officer.
    """
    if not pages:
        raise ValueError("No pages supplied")

    first_rows = _group_into_rows(pages[0].spans)
    bank_name_row = first_rows[0] if first_rows else []
    bank_name = (
        _find_label(first_rows, "Bank Name") or " ".join(s.text for s in bank_name_row).strip()
    )

    holder = _find_label(first_rows, "Account Holder")
    account_number = _find_label(first_rows, "Account Number")
    period_text = next(
        (
            " ".join(s.text for s in row)
            for row in first_rows
            if any("Statement Period" in s.text for s in row)
        ),
        None,
    )
    if not (holder and account_number and period_text):
        raise ValueError(
            "Missing required header fields (holder/account/period). "
            "Document may not be a supported bank statement."
        )
    match = PERIOD_RE.search(period_text)
    if not match:
        raise ValueError(f"Could not parse statement period from: {period_text!r}")
    period_start = _parse_period(match.group(1))
    period_end = _parse_period(match.group(2))

    transactions: list[Transaction] = []
    for parsed in pages:
        rows = _group_into_rows(parsed.spans)
        if not any(_row_is_transaction(row) for row in rows):
            continue
        columns = _detect_transaction_columns(rows)
        for row in rows:
            if _row_is_transaction(row):
                transactions.append(_parse_transaction_row(row, parsed.page, columns))

    last_rows = _group_into_rows(pages[-1].spans)
    opening = _find_money_after(last_rows, "Opening Balance")
    total_debits = _find_money_after(last_rows, "Total Debits")
    total_credits = _find_money_after(last_rows, "Total Credits")
    closing = _find_money_after(last_rows, "Closing Balance")
    if None in (opening, total_debits, total_credits, closing):
        raise ValueError("Missing required footer totals")

    return BankStatement(
        bank_name=bank_name,
        account_holder=holder,
        account_number=account_number,
        statement_period_start=period_start,
        statement_period_end=period_end,
        opening_balance=opening,  # type: ignore[arg-type]
        closing_balance=closing,  # type: ignore[arg-type]
        total_credits=total_credits,  # type: ignore[arg-type]
        total_debits=total_debits,  # type: ignore[arg-type]
        transactions=transactions,
        source_fields={
            "bank_name": source_location(bank_name_row),
            **labelled_sources(
                first_rows,
                {
                    "Bank Name": "bank_name",
                    "Account Holder": "account_holder",
                    "Account Number": "account_number",
                    "Statement Period": "statement_period",
                },
            ),
            **labelled_sources(
                last_rows,
                {
                    "Opening Balance": "opening_balance",
                    "Closing Balance": "closing_balance",
                    "Total Credits": "total_credits",
                    "Total Debits": "total_debits",
                },
            ),
        },
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from app.ingestion.parser import parse_pdf

    target = Path(sys.argv[1])
    pages = parse_pdf(target)
    statement = extract_bank_statement(pages)
    print(statement.model_dump_json(indent=2))
