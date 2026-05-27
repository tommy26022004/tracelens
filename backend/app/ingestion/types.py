"""Shared dataclasses / Pydantic models for ingestion outputs.

Keeping these in a leaf module avoids circular imports between parser,
extractor, chunker, and store.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class DocumentKind(str, Enum):
    """Document categories the pipeline can route."""

    BANK_STATEMENT = "bank_statement"
    SSM_REGISTRATION = "ssm_registration"
    AUDITED_FINANCIALS = "audited_financials"
    TAX_RETURN = "tax_return"
    UNKNOWN = "unknown"


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


class Director(BaseModel):
    """One director / officer listed on an SSM form."""

    name: str
    nric_or_passport: str | None = None
    role: str | None = None


class SSMRegistration(BaseModel):
    """Structured form of a Malaysian SSM registration document.

    Captures the fields a loan officer cares about: legal identity, age
    of the business, and capital structure. Director list is included
    because related-party risk is part of the 5C Character assessment.
    """

    company_name: str
    registration_number: str
    incorporation_date: date
    company_type: str = Field(
        description="e.g. SDN BHD, BERHAD, ENTERPRISE, PARTNERSHIP"
    )
    business_address: str
    paid_up_capital: Decimal
    directors: list[Director]
    page_count: int = 1
