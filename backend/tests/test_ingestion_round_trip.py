"""Generator → parser → extractor round-trip test.

If this passes, the extractor recovers the exact synthetic statement.
This gives us a ground-truth baseline against which the LLM-assisted
extractor (Phase 3) and the real-PDF extractor (Phase 6 evaluation)
can be measured.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.extractor import (
    _detect_transaction_columns,
    _group_into_rows,
    _parse_transaction_row,
    extract_bank_statement,
)
from app.ingestion.parser import TextSpan, parse_pdf
from app.ingestion.synthetic import GeneratorConfig, generate


@pytest.fixture
def synthetic_pair(tmp_path: Path) -> tuple[Path, Path]:
    pdf, gt = generate(GeneratorConfig(seed=7), tmp_path)
    return pdf, gt


def test_extractor_matches_ground_truth(synthetic_pair: tuple[Path, Path]) -> None:
    from app.ingestion.types import BankStatement

    pdf_path, gt_path = synthetic_pair
    expected = BankStatement.model_validate_json(gt_path.read_text())
    actual = extract_bank_statement(parse_pdf(pdf_path))

    assert actual.bank_name == expected.bank_name
    assert actual.account_holder == expected.account_holder
    assert actual.account_number == expected.account_number
    assert actual.statement_period_start == expected.statement_period_start
    assert actual.statement_period_end == expected.statement_period_end
    assert actual.opening_balance == expected.opening_balance
    assert actual.closing_balance == expected.closing_balance
    assert actual.total_credits == expected.total_credits
    assert actual.total_debits == expected.total_debits

    assert len(actual.transactions) == len(expected.transactions)
    for got, want in zip(actual.transactions, expected.transactions, strict=True):
        assert got.txn_date == want.txn_date
        assert got.debit == want.debit
        assert got.credit == want.credit
        assert got.balance == want.balance
        assert got.page == want.page
        # description may pick up extra whitespace; compare normalised
        assert " ".join(got.description.split()) == " ".join(want.description.split())


def test_paginated_statement_recovers_all_rows(tmp_path: Path) -> None:
    """A heavy statement that spans 2+ pages must still extract every row."""
    cfg = GeneratorConfig(seed=11, n_transactions=80)
    pdf, gt = generate(cfg, tmp_path)
    expected_count = len(__import__("json").loads(gt.read_text())["transactions"])
    actual = extract_bank_statement(parse_pdf(pdf))
    assert len(actual.transactions) == expected_count
    # Last transaction's balance must match the declared closing balance —
    # the strongest single check that no row was dropped or duplicated.
    assert actual.transactions[-1].balance == actual.closing_balance


def test_transaction_columns_follow_shifted_headers() -> None:
    def span(text: str, x: float, y: float) -> TextSpan:
        return TextSpan(text=text, page=1, bbox=(x, y, x + 40, y + 10))

    spans = [
        span("Date", 20, 100),
        span("Description", 90, 100),
        span("Debit (RM)", 510, 100),
        span("Credit (RM)", 590, 100),
        span("Balance (RM)", 680, 100),
        span("01/01/2025", 20, 125),
        span("CUSTOMER RECEIPT", 90, 125),
        span("2,000.00", 590, 125),
        span("12,000.00", 680, 125),
        span("02/01/2025", 20, 150),
        span("SUPPLIER PAYMENT", 90, 150),
        span("1,200.00", 510, 150),
        span("10,800.00", 680, 150),
    ]
    rows = _group_into_rows(spans)
    columns = _detect_transaction_columns(rows)
    credit = _parse_transaction_row(rows[1], 1, columns)
    debit = _parse_transaction_row(rows[2], 1, columns)

    assert credit.credit == Decimal("2000.00")
    assert credit.debit is None
    assert credit.balance == Decimal("12000.00")
    assert debit.debit == Decimal("1200.00")
    assert debit.credit is None
    assert debit.balance == Decimal("10800.00")


def test_transaction_columns_split_merged_header_span() -> None:
    spans = [
        TextSpan("DATE", 1, (20, 100, 60, 110)),
        TextSpan("DESCRIPTION", 1, (90, 100, 180, 110)),
        TextSpan("DEBIT (RM)", 1, (430, 100, 490, 110)),
        TextSpan("CREDIT (RM) BALANCE (RM)", 1, (500, 100, 700, 110)),
    ]
    columns = _detect_transaction_columns([spans])

    assert columns.debit < columns.credit < columns.balance


def test_extractor_rejects_non_statement(tmp_path: Path) -> None:
    """A PDF without the expected header should raise, not silently misextract."""
    import pymupdf

    empty = tmp_path / "empty.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(empty)
    doc.close()

    with pytest.raises(ValueError):
        extract_bank_statement(parse_pdf(empty))
