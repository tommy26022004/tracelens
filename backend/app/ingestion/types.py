"""Shared dataclasses / Pydantic models for ingestion outputs.

Keeping these in a leaf module avoids circular imports between parser,
extractor, chunker, and store.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """One row from a bank statement."""

    txn_date: date
    description: str
    debit: Decimal | None = None
    credit: Decimal | None = None
    balance: Decimal
    page: int = Field(description="1-indexed source page for citation traceability")


class BankStatement(BaseModel):
    """Structured form of a single monthly bank statement."""

    bank_name: str
    account_holder: str
    account_number: str
    statement_period_start: date
    statement_period_end: date
    opening_balance: Decimal
    closing_balance: Decimal
    total_credits: Decimal
    total_debits: Decimal
    transactions: list[Transaction]

    @property
    def deposit_count(self) -> int:
        return sum(1 for t in self.transactions if t.credit is not None)
