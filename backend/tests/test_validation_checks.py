"""Deterministic validation tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.ingestion.types import BankStatement, Transaction
from app.validation.checks import Severity, run_checks


def _stmt(transactions: list[Transaction], **overrides) -> BankStatement:
    defaults = dict(
        bank_name="Synthetic Bank Berhad",
        account_holder="ACME TRADING SDN BHD",
        account_number="5141-2233-4455",
        statement_period_start=date(2026, 1, 1),
        statement_period_end=date(2026, 1, 31),
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1050.00"),
        total_credits=Decimal("100.00"),
        total_debits=Decimal("50.00"),
        transactions=transactions,
    )
    defaults.update(overrides)
    return BankStatement(**defaults)


def test_balance_arithmetic_flags_mismatch() -> None:
    stmt = _stmt([], closing_balance=Decimal("999.99"))
    issues = run_checks([stmt], ["doc-1"])
    codes = {i.code for i in issues}
    assert "BALANCE_ARITHMETIC" in codes
    critical = [i for i in issues if i.code == "BALANCE_ARITHMETIC"]
    assert critical[0].severity is Severity.CRITICAL
    assert critical[0].citations == ["doc-1:summary:0"]


def test_running_balance_flags_bad_row() -> None:
    txns = [
        Transaction(
            txn_date=date(2026, 1, 5),
            description="DEPOSIT",
            debit=None,
            credit=Decimal("100.00"),
            balance=Decimal("9999.00"),  # wrong — should be 1100
            page=1,
        )
    ]
    stmt = _stmt(txns)
    issues = run_checks([stmt], ["doc-1"])
    assert any(i.code == "RUNNING_BALANCE" for i in issues)


def test_date_outside_period_is_flagged() -> None:
    txns = [
        Transaction(
            txn_date=date(2025, 12, 30),  # before period_start
            description="WITHDRAWAL",
            debit=Decimal("50.00"),
            credit=None,
            balance=Decimal("950.00"),
            page=1,
        ),
        Transaction(
            txn_date=date(2026, 1, 10),
            description="DEPOSIT",
            debit=None,
            credit=Decimal("100.00"),
            balance=Decimal("1050.00"),
            page=1,
        ),
    ]
    stmt = _stmt(txns)
    issues = run_checks([stmt], ["doc-1"])
    assert any(i.code == "DATE_OUTSIDE_PERIOD" for i in issues)


def test_clean_statement_produces_no_issues() -> None:
    txns = [
        Transaction(
            txn_date=date(2026, 1, 5),
            description="DEPOSIT",
            debit=None,
            credit=Decimal("100.00"),
            balance=Decimal("1100.00"),
            page=1,
        ),
        Transaction(
            txn_date=date(2026, 1, 10),
            description="WITHDRAWAL",
            debit=Decimal("50.00"),
            credit=None,
            balance=Decimal("1050.00"),
            page=1,
        ),
    ]
    stmt = _stmt(txns)
    issues = run_checks([stmt], ["doc-1"])
    assert issues == []


def test_duplicate_transactions_flagged_as_info() -> None:
    txns = [
        Transaction(
            txn_date=date(2026, 1, 5),
            description="VENDOR PAYMENT",
            debit=Decimal("25.00"),
            credit=None,
            balance=Decimal("1075.00"),
            page=1,
        ),
        Transaction(
            txn_date=date(2026, 1, 5),
            description="VENDOR PAYMENT",
            debit=Decimal("25.00"),
            credit=None,
            balance=Decimal("1050.00"),
            page=1,
        ),
    ]
    stmt = _stmt(txns, total_debits=Decimal("50.00"), total_credits=Decimal("100.00"))
    issues = run_checks([stmt], ["doc-1"])
    dups = [i for i in issues if i.code == "POSSIBLE_DUPLICATE"]
    assert dups, "Expected POSSIBLE_DUPLICATE inconsistency"
    assert dups[0].severity is Severity.INFO
    assert len(dups[0].citations) == 2
