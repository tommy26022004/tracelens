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
    MANAGEMENT_ACCOUNTS = "management_accounts"
    CASH_FLOW_FORECAST = "cash_flow_forecast"
    FACILITY_STATEMENT = "facility_statement"
    UNKNOWN = "unknown"


__all__ = [
    "DocumentKind",
    "Transaction",
    "BankStatement",
    "Director",
    "SSMRegistration",
    "FinancialPeriod",
    "AuditedFinancials",
    "TaxReturn",
]


class SourceLocation(BaseModel):
    page: int = Field(ge=1)
    text: str
    bbox: tuple[float, float, float, float]


class Transaction(BaseModel):
    """One row from a bank statement."""

    txn_date: date
    description: str
    reference_no: str | None = None
    debit: Decimal | None = None
    credit: Decimal | None = None
    balance: Decimal
    page: int = Field(description="1-indexed source page for citation traceability")
    source: SourceLocation | None = None


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
    source_fields: dict[str, SourceLocation] = Field(default_factory=dict)

    @property
    def deposit_count(self) -> int:
        return sum(1 for t in self.transactions if t.credit is not None)


class FinancialPeriod(BaseModel):
    """One reporting period's worth of figures from an audited statement.

    Captured at the granularity a credit officer cares about — anything
    finer (segment reporting, FX, deferred tax) is left for human review.
    """

    period_end: date = Field(description="Financial year end")
    revenue: Decimal
    cost_of_sales: Decimal
    gross_profit: Decimal
    operating_expenses: Decimal
    ebit: Decimal = Field(description="Earnings before interest and tax")
    interest_expense: Decimal
    net_profit: Decimal
    # Balance sheet
    current_assets: Decimal
    non_current_assets: Decimal
    current_liabilities: Decimal
    non_current_liabilities: Decimal
    total_equity: Decimal
    # Cash flow
    cash_from_operations: Decimal
    source_fields: dict[str, SourceLocation] = Field(default_factory=dict)

    @property
    def total_assets(self) -> Decimal:
        return self.current_assets + self.non_current_assets

    @property
    def total_liabilities(self) -> Decimal:
        return self.current_liabilities + self.non_current_liabilities


class AuditedFinancials(BaseModel):
    """An audited financial statement package — typically two years.

    Two consecutive years is the Malaysian SME convention so we can
    derive year-over-year growth rates inside ratio analysis without
    going back to source data.
    """

    company_name: str
    auditor: str
    financial_year_end: date
    periods: list[FinancialPeriod] = Field(description="Most recent period first, then comparative")
    display_unit: str = "RM"
    canonical_unit: str = "RM"
    unit_multiplier: Decimal = Decimal("1")
    page_count: int = 1
    source_fields: dict[str, SourceLocation] = Field(default_factory=dict)


class TaxReturn(BaseModel):
    """A Malaysian Form C tax return (company income tax).

    Form C reports `chargeable_income` rather than gross revenue — the
    cross-doc check compares this against the audited financials and
    against bank-statement deposits as a triangulation signal.
    """

    company_name: str
    tax_reference_number: str
    year_of_assessment: int
    gross_business_income: Decimal
    chargeable_income: Decimal
    tax_payable: Decimal
    page_count: int = 1
    source_fields: dict[str, SourceLocation] = Field(default_factory=dict)


class Director(BaseModel):
    """One director / officer listed on an SSM form."""

    name: str
    nric_or_passport: str | None = None
    role: str | None = None
    source: SourceLocation | None = None


class SSMRegistration(BaseModel):
    """Structured form of a Malaysian SSM registration document.

    Captures the fields a loan officer cares about: legal identity, age
    of the business, and capital structure. Director list is included
    because related-party risk is part of the 5C Character assessment.
    """

    company_name: str
    registration_number: str
    incorporation_date: date
    company_type: str = Field(description="e.g. SDN BHD, BERHAD, ENTERPRISE, PARTNERSHIP")
    business_address: str
    paid_up_capital: Decimal
    directors: list[Director]
    page_count: int = 1
    source_fields: dict[str, SourceLocation] = Field(default_factory=dict)
