"""Deterministic validation tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.ingestion.types import BankStatement, Director, SSMRegistration, Transaction
from app.validation.checks import Severity, run_checks
from app.validation.cross_doc import run_cross_doc_checks


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


def _ssm(company_name: str, incorporation: date = date(2024, 1, 15)) -> SSMRegistration:
    return SSMRegistration(
        company_name=company_name,
        registration_number="202401000123 (1500123-X)",
        incorporation_date=incorporation,
        company_type="SDN BHD",
        business_address="Lot 12, KL",
        paid_up_capital=Decimal("100000.00"),
        directors=[Director(name="A B", nric_or_passport="x", role="Director")],
    )


def test_cross_doc_holder_matches_ssm() -> None:
    stmt = _stmt([], opening_balance=Decimal("1000.00"), closing_balance=Decimal("1000.00"),
                 total_credits=Decimal("0"), total_debits=Decimal("0"))
    # Bank account holder uses "S/B" abbreviation; SSM uses "SDN BHD" — should still match.
    stmt = stmt.model_copy(update={"account_holder": "ACME TRADING S/B"})
    ssm = _ssm("ACME TRADING SDN BHD")
    issues = run_cross_doc_checks([stmt], ["bank-1"], [ssm], ["ssm-1"])
    assert not any(i.code == "HOLDER_SSM_MISMATCH" for i in issues)


def test_cross_doc_holder_mismatch_is_critical() -> None:
    stmt = _stmt([], opening_balance=Decimal("1000.00"), closing_balance=Decimal("1000.00"),
                 total_credits=Decimal("0"), total_debits=Decimal("0"))
    stmt = stmt.model_copy(update={"account_holder": "BETA CORP SDN BHD"})
    ssm = _ssm("ACME TRADING SDN BHD")
    issues = run_cross_doc_checks([stmt], ["bank-1"], [ssm], ["ssm-1"])
    mismatch = [i for i in issues if i.code == "HOLDER_SSM_MISMATCH"]
    assert len(mismatch) == 1
    assert mismatch[0].severity is Severity.CRITICAL
    # Citation must point at both the bank and SSM summary chunks.
    assert "bank-1:summary:0" in mismatch[0].citations
    assert "ssm-1:summary:0" in mismatch[0].citations


def test_cross_doc_activity_before_incorporation() -> None:
    stmt = _stmt(
        [],
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1000.00"),
        total_credits=Decimal("0"),
        total_debits=Decimal("0"),
        statement_period_start=date(2023, 6, 1),
        statement_period_end=date(2023, 6, 30),
    )
    stmt = stmt.model_copy(update={"account_holder": "ACME TRADING SDN BHD"})
    ssm = _ssm("ACME TRADING SDN BHD", incorporation=date(2024, 1, 15))
    issues = run_cross_doc_checks([stmt], ["bank-1"], [ssm], ["ssm-1"])
    assert any(i.code == "ACTIVITY_BEFORE_INCORPORATION" for i in issues)


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
