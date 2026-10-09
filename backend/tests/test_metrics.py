"""Bank-statement metric tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.ingestion.types import BankStatement, Transaction
from app.ratios.bank_statement_metrics import compute_metrics


def test_metrics_basic_arithmetic() -> None:
    stmt = BankStatement(
        bank_name="X",
        account_holder="Y",
        account_number="1",
        statement_period_start=date(2026, 1, 1),
        statement_period_end=date(2026, 1, 31),
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1050.00"),
        total_credits=Decimal("100.00"),
        total_debits=Decimal("50.00"),
        transactions=[
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
        ],
    )
    m = compute_metrics(stmt, document_id="doc-1")
    assert m.document_id == "doc-1"
    assert m.period_days == 31
    assert m.transaction_count == 2
    assert m.net_change == Decimal("50.00")
    assert m.deposit_count == 1
    assert m.withdrawal_count == 1
    assert m.largest_credit == Decimal("100.00")
    assert m.largest_debit == Decimal("50.00")
    assert m.is_cash_positive
