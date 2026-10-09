"""Coherent synthetic company data shared by every PDF generator.

The object in this module is the single source of truth for legal identity,
audited figures, tax figures, and bank cash movement. Scenario generation may
replace selected fields deliberately, but the default package reconciles across
all four document types.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.ingestion.types import Director, FinancialPeriod

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CoherentFinancials:
    """A complete synthetic SME profile used across a loan package."""

    scenario_id: int = 1
    company_name: str = "ACME TRADING SDN BHD"
    bank_account_holder: str = "ACME TRADING SDN BHD"
    audited_company_name: str = "ACME TRADING SDN BHD"
    tax_company_name: str = "ACME TRADING SDN BHD"
    registration_number: str = "202401000123 (1500123-X)"
    tax_reference_number: str = "C 1234567890"
    account_number: str = "514122334455"
    incorporation_date: date = date(2024, 1, 15)
    business_address: str = "Lot 12-3, Jalan Damansara, 50490 Kuala Lumpur"
    registered_office: str = "Suite 8-2, Jalan Tun Razak, 50400 Kuala Lumpur"
    business_nature: str = "Wholesale trading and distribution of industrial supplies"
    auditor: str = "Synthetic Audit Partners PLT"
    auditor_number: str = "AF 009999"
    audit_date: date = date(2026, 3, 20)
    financial_year_end: date = date(2025, 12, 31)
    statement_start: date = date(2026, 1, 1)
    opening_bank_balance: Decimal = Decimal("125000.00")
    directors: tuple[Director, ...] = field(
        default=(
            Director(
                name="AHMAD BIN ABDULLAH",
                nric_or_passport="850102-14-1234",
                role="Managing Director",
            ),
            Director(
                name="LIM WEI MING",
                nric_or_passport="880515-08-5678",
                role="Director",
            ),
        )
    )
    shareholder_percentages: tuple[Decimal, ...] = (
        Decimal("60.00"),
        Decimal("40.00"),
    )
    revenue: Decimal = Decimal("1800000.00")
    prior_revenue: Decimal = Decimal("1607142.86")
    cost_of_sales: Decimal = Decimal("1080000.00")
    salaries: Decimal = Decimal("240000.00")
    rental_expense: Decimal = Decimal("60000.00")
    depreciation: Decimal = Decimal("45000.00")
    administrative_expenses: Decimal = Decimal("90000.00")
    finance_costs: Decimal = Decimal("36000.00")
    tax_expense: Decimal = Decimal("59760.00")
    ppe: Decimal = Decimal("400000.00")
    intangible_assets: Decimal = Decimal("20000.00")
    trade_receivables: Decimal = Decimal("300000.00")
    cash_and_bank: Decimal = Decimal("200000.00")
    inventories: Decimal = Decimal("180000.00")
    trade_payables: Decimal = Decimal("180000.00")
    short_term_borrowings: Decimal = Decimal("120000.00")
    tax_payable_balance: Decimal = Decimal("30000.00")
    long_term_borrowings: Decimal = Decimal("220000.00")
    paid_up_capital: Decimal = Decimal("250000.00")
    retained_earnings: Decimal = Decimal("300000.00")
    cash_from_operations: Decimal = Decimal("260000.00")
    cash_from_investing: Decimal = Decimal("-70000.00")
    cash_from_financing: Decimal = Decimal("-45000.00")
    tax_gross_business_income: Decimal = Decimal("1800000.00")
    tax_chargeable_income: Decimal = Decimal("249000.00")
    tax_instalments_paid: Decimal = Decimal("50000.00")
    bank_credit_multiplier: Decimal = Decimal("1.00")
    bank_debit_ratio: Decimal = Decimal("0.82")
    missing_fields: tuple[str, ...] = ()

    @property
    def operating_expenses(self) -> Decimal:
        return money(
            self.salaries + self.rental_expense + self.depreciation + self.administrative_expenses
        )

    @property
    def gross_profit(self) -> Decimal:
        return money(self.revenue - self.cost_of_sales)

    @property
    def ebit(self) -> Decimal:
        return money(self.gross_profit - self.operating_expenses)

    @property
    def profit_before_tax(self) -> Decimal:
        return money(self.ebit - self.finance_costs)

    @property
    def net_profit(self) -> Decimal:
        return money(self.profit_before_tax - self.tax_expense)

    @property
    def current_assets(self) -> Decimal:
        return money(self.trade_receivables + self.cash_and_bank + self.inventories)

    @property
    def non_current_assets(self) -> Decimal:
        return money(self.ppe + self.intangible_assets)

    @property
    def current_liabilities(self) -> Decimal:
        return money(self.trade_payables + self.short_term_borrowings + self.tax_payable_balance)

    @property
    def non_current_liabilities(self) -> Decimal:
        return money(self.long_term_borrowings)

    @property
    def total_equity(self) -> Decimal:
        return money(self.paid_up_capital + self.retained_earnings)

    @property
    def tax_payable(self) -> Decimal:
        return money(self.tax_chargeable_income * Decimal("0.24"))

    def bank_credits_for_days(self, days: int) -> Decimal:
        annual_fraction = Decimal(days) / Decimal(365)
        return money(self.tax_gross_business_income * annual_fraction * self.bank_credit_multiplier)

    def current_period(self) -> FinancialPeriod:
        return FinancialPeriod(
            period_end=self.financial_year_end,
            revenue=self.revenue,
            cost_of_sales=self.cost_of_sales,
            gross_profit=self.gross_profit,
            operating_expenses=self.operating_expenses,
            ebit=self.ebit,
            interest_expense=self.finance_costs,
            net_profit=self.net_profit,
            current_assets=self.current_assets,
            non_current_assets=self.non_current_assets,
            current_liabilities=self.current_liabilities,
            non_current_liabilities=self.non_current_liabilities,
            total_equity=self.total_equity,
            cash_from_operations=self.cash_from_operations,
        )

    def prior_period(self) -> FinancialPeriod:
        scale = self.prior_revenue / self.revenue if self.revenue else Decimal("1")
        prior_end = self.financial_year_end.replace(year=self.financial_year_end.year - 1)
        current = self.current_period()
        return FinancialPeriod(
            period_end=prior_end,
            revenue=self.prior_revenue,
            cost_of_sales=money(current.cost_of_sales * scale),
            gross_profit=money(current.gross_profit * scale),
            operating_expenses=money(current.operating_expenses * scale),
            ebit=money(current.ebit * scale),
            interest_expense=money(current.interest_expense * scale),
            net_profit=money(current.net_profit * scale),
            current_assets=money(current.current_assets * scale),
            non_current_assets=money(current.non_current_assets * scale),
            current_liabilities=money(current.current_liabilities * scale),
            non_current_liabilities=money(current.non_current_liabilities * scale),
            total_equity=money(current.total_equity * scale),
            cash_from_operations=money(current.cash_from_operations * scale),
        )

    def with_changes(self, **changes: object) -> CoherentFinancials:
        return replace(self, **changes)


def default_coherent_financials() -> CoherentFinancials:
    return CoherentFinancials()
