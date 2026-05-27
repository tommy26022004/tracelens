"""Generator → parser → extractor round-trip test.

If this passes, the extractor recovers the exact synthetic statement.
This gives us a ground-truth baseline against which the LLM-assisted
extractor (Phase 3) and the real-PDF extractor (Phase 6 evaluation)
can be measured.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.extractor import extract_bank_statement
from app.ingestion.parser import parse_pdf
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
