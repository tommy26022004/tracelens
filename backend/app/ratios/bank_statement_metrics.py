"""Metrics derivable from bank statements alone.

These feed Capacity (cash-flow availability), Character (deposit
regularity), and the early-warning section of the risk summary. They
are not 5C ratios — those need audited financials — but they are the
strongest signal a loan officer gets purely from bank statements.
"""

from __future__ import annotations

from decimal import Decimal
from statistics import pstdev

from pydantic import BaseModel, Field

from app.ingestion.types import BankStatement


class BankStatementMetrics(BaseModel):
    document_id: str
    period_days: int
    transaction_count: int
    total_credits: Decimal
    total_debits: Decimal
    net_change: Decimal = Field(description="closing − opening")
    avg_daily_inflow: Decimal
    avg_daily_outflow: Decimal
    deposit_count: int
    withdrawal_count: int
    largest_credit: Decimal | None
    largest_debit: Decimal | None
    end_of_period_balance: Decimal
    balance_volatility: Decimal = Field(
        description="Population stddev of end-of-day balance (RM)"
    )

    @property
    def is_cash_positive(self) -> bool:
        return self.net_change > 0


def _quantise(value: Decimal) -> Decimal:
    """Round to 2 decimal places, matching MYR cents precision."""
    return value.quantize(Decimal("0.01"))


def compute_metrics(stmt: BankStatement, document_id: str) -> BankStatementMetrics:
    period_days = (stmt.statement_period_end - stmt.statement_period_start).days + 1
    if period_days < 1:
        raise ValueError("Statement end date precedes its start date")
    credits = [t.credit for t in stmt.transactions if t.credit is not None]
    debits = [t.debit for t in stmt.transactions if t.debit is not None]
    balances = [float(t.balance) for t in stmt.transactions]

    volatility = Decimal(str(pstdev(balances))) if len(balances) > 1 else Decimal(0)

    return BankStatementMetrics(
        document_id=document_id,
        period_days=period_days,
        transaction_count=len(stmt.transactions),
        total_credits=_quantise(stmt.total_credits),
        total_debits=_quantise(stmt.total_debits),
        net_change=_quantise(stmt.closing_balance - stmt.opening_balance),
        avg_daily_inflow=_quantise(stmt.total_credits / Decimal(period_days)),
        avg_daily_outflow=_quantise(stmt.total_debits / Decimal(period_days)),
        deposit_count=len(credits),
        withdrawal_count=len(debits),
        largest_credit=max(credits) if credits else None,
        largest_debit=max(debits) if debits else None,
        end_of_period_balance=_quantise(stmt.closing_balance),
        balance_volatility=_quantise(volatility),
    )
