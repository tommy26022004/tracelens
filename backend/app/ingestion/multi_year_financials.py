"""Coherent multi-year and multi-account synthetic company model."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.ingestion.coherent_financials import CoherentFinancials, money
from app.ingestion.types import Director, FinancialPeriod


class BankAccountProfile(BaseModel):
    account_id: str
    bank_name: str
    account_number: str
    active_months: tuple[int, ...]
    credit_weight: Decimal = Field(gt=0)
    opening_balance: Decimal

    @model_validator(mode="after")
    def validate_months(self) -> BankAccountProfile:
        if not self.active_months:
            raise ValueError("active_months cannot be empty")
        if any(month < 1 or month > 12 for month in self.active_months):
            raise ValueError("active_months must contain calendar months 1-12")
        if len(set(self.active_months)) != len(self.active_months):
            raise ValueError("active_months must be unique")
        return self


class FinancialYearSnapshot(BaseModel):
    financial_period: FinancialPeriod
    tax_gross_business_income: Decimal
    tax_chargeable_income: Decimal
    tax_payable: Decimal

    @property
    def year(self) -> int:
        return self.financial_period.period_end.year

    @property
    def accounting_equation_delta(self) -> Decimal:
        period = self.financial_period
        return money(period.total_assets - period.total_liabilities - period.total_equity)


class MultiYearCoherentFinancials(BaseModel):
    company_name: str
    registration_number: str
    tax_reference_number: str
    incorporation_date: date
    business_address: str
    registered_office: str
    business_nature: str
    auditor: str
    auditor_number: str
    directors: list[Director]
    accounts: list[BankAccountProfile] = Field(min_length=1)
    years: list[FinancialYearSnapshot] = Field(min_length=1)
    base_financials: CoherentFinancials

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def validate_coherence(self) -> MultiYearCoherentFinancials:
        account_ids = [account.account_id for account in self.accounts]
        account_numbers = [account.account_number for account in self.accounts]
        years = [snapshot.year for snapshot in self.years]
        if len(set(account_ids)) != len(account_ids):
            raise ValueError("account_id values must be unique")
        if len(set(account_numbers)) != len(account_numbers):
            raise ValueError("account numbers must be unique")
        if len(set(years)) != len(years):
            raise ValueError("financial years must be unique")
        if any(snapshot.accounting_equation_delta != 0 for snapshot in self.years):
            raise ValueError("every financial year must satisfy the accounting equation")
        return self

    def snapshot(self, year: int) -> FinancialYearSnapshot:
        for snapshot in self.years:
            if snapshot.year == year:
                return snapshot
        raise KeyError(f"Financial year {year} is not available")

    def monthly_credit_targets(self, year: int) -> dict[tuple[str, int], Decimal]:
        """Allocate annual revenue across active accounts without double-counting."""
        annual_revenue = self.snapshot(year).tax_gross_business_income
        monthly_total = money(annual_revenue / Decimal(12))
        allocations: dict[tuple[str, int], Decimal] = {}
        allocated_total = Decimal(0)
        for month in range(1, 13):
            active = [account for account in self.accounts if month in account.active_months]
            if not active:
                raise ValueError(f"No active bank account for month {month}")
            total_weight = sum((account.credit_weight for account in active), Decimal(0))
            month_allocations = [
                money(monthly_total * account.credit_weight / total_weight) for account in active
            ]
            month_allocations[-1] = money(
                month_allocations[-1] + monthly_total - sum(month_allocations, Decimal(0))
            )
            for account, amount in zip(active, month_allocations, strict=True):
                allocations[(account.account_id, month)] = amount
                allocated_total += amount
        annual_delta = money(annual_revenue - allocated_total)
        final_key = next(reversed(allocations))
        allocations[final_key] = money(allocations[final_key] + annual_delta)
        return allocations


def _scaled_period(base: FinancialPeriod, year: int, scale: Decimal) -> FinancialPeriod:
    return FinancialPeriod(
        period_end=base.period_end.replace(year=year),
        revenue=money(base.revenue * scale),
        cost_of_sales=money(base.cost_of_sales * scale),
        gross_profit=money(base.gross_profit * scale),
        operating_expenses=money(base.operating_expenses * scale),
        ebit=money(base.ebit * scale),
        interest_expense=money(base.interest_expense * scale),
        net_profit=money(base.net_profit * scale),
        current_assets=money(base.current_assets * scale),
        non_current_assets=money(base.non_current_assets * scale),
        current_liabilities=money(base.current_liabilities * scale),
        non_current_liabilities=money(base.non_current_liabilities * scale),
        total_equity=money(base.total_equity * scale),
        cash_from_operations=money(base.cash_from_operations * scale),
    )


def build_default_multi_year_financials(
    base: CoherentFinancials | None = None,
) -> MultiYearCoherentFinancials:
    base = base or CoherentFinancials()
    current = base.current_period()
    scales = {2023: Decimal("0.78"), 2024: Decimal("0.89"), 2025: Decimal("1.00")}
    snapshots = []
    for year, scale in scales.items():
        period = _scaled_period(current, year, scale)
        chargeable = money(base.tax_chargeable_income * scale)
        snapshots.append(
            FinancialYearSnapshot(
                financial_period=period,
                tax_gross_business_income=period.revenue,
                tax_chargeable_income=chargeable,
                tax_payable=money(chargeable * Decimal("0.24")),
            )
        )
    return MultiYearCoherentFinancials(
        company_name=base.company_name,
        registration_number=base.registration_number,
        tax_reference_number=base.tax_reference_number,
        incorporation_date=base.incorporation_date,
        business_address=base.business_address,
        registered_office=base.registered_office,
        business_nature=base.business_nature,
        auditor=base.auditor,
        auditor_number=base.auditor_number,
        directors=list(base.directors),
        accounts=[
            BankAccountProfile(
                account_id="operating_account",
                bank_name="MAYBANK BERHAD",
                account_number=base.account_number,
                active_months=tuple(range(1, 13)),
                credit_weight=Decimal("0.75"),
                opening_balance=base.opening_bank_balance,
            ),
            BankAccountProfile(
                account_id="collection_account",
                bank_name="CIMB BANK BERHAD",
                account_number="800112223334",
                active_months=(7, 8, 9, 10, 11, 12),
                credit_weight=Decimal("0.25"),
                opening_balance=Decimal("25000.00"),
            ),
        ],
        years=snapshots,
        base_financials=base,
    )
