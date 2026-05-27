"""Cross-doc checks introduced with audited financials + tax return."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.ingestion.types import (
    AuditedFinancials,
    BankStatement,
    Director,
    FinancialPeriod,
    SSMRegistration,
    TaxReturn,
)
from app.validation.checks import Severity
from app.validation.cross_doc import run_cross_doc_checks


def _stmt(holder: str = "ACME TRADING SDN BHD", credits: Decimal = Decimal("150000")) -> BankStatement:
    return BankStatement(
        bank_name="Synthetic Bank",
        account_holder=holder,
        account_number="1",
        statement_period_start=date(2025, 1, 1),
        statement_period_end=date(2025, 1, 31),
        opening_balance=Decimal("1000"),
        closing_balance=Decimal("1000") + credits,
        total_credits=credits,
        total_debits=Decimal("0"),
        transactions=[],
    )


def _ssm(name: str = "ACME TRADING SDN BHD") -> SSMRegistration:
    return SSMRegistration(
        company_name=name,
        registration_number="202401000123 (1500123-X)",
        incorporation_date=date(2024, 1, 1),
        company_type="SDN BHD",
        business_address="KL",
        paid_up_capital=Decimal("100000"),
        directors=[Director(name="A B", nric_or_passport="x", role="Director")],
    )


def _fin(
    company: str = "ACME TRADING SDN BHD", revenue: Decimal = Decimal("1800000")
) -> AuditedFinancials:
    period = FinancialPeriod(
        period_end=date(2025, 12, 31),
        revenue=revenue,
        cost_of_sales=revenue / 2,
        gross_profit=revenue / 2,
        operating_expenses=revenue / 5,
        ebit=revenue / 5,
        interest_expense=revenue / 50,
        net_profit=revenue / 10,
        current_assets=revenue / 3,
        non_current_assets=revenue / 2,
        current_liabilities=revenue / 5,
        non_current_liabilities=revenue / 4,
        total_equity=revenue / 4,
        cash_from_operations=revenue / 4,
    )
    return AuditedFinancials(
        company_name=company,
        auditor="Synthetic Audit",
        financial_year_end=date(2025, 12, 31),
        periods=[period],
    )


def _tax(income: Decimal, year: int = 2025) -> TaxReturn:
    return TaxReturn(
        company_name="ACME TRADING SDN BHD",
        tax_reference_number="C 2500001234",
        year_of_assessment=year,
        gross_business_income=income,
        chargeable_income=income / 5,
        tax_payable=income / 20,
    )


def test_declared_income_far_below_deposits_is_flagged() -> None:
    """Annualised credits ~RM 1.8M but tax declares RM 0.5M -> WARNING."""
    stmt = _stmt(credits=Decimal("150000"))  # 150k / 30 days * 365 ≈ 1.83M
    tax = _tax(income=Decimal("500000"))
    issues = run_cross_doc_checks(
        [stmt],
        ["bank-1"],
        [],
        [],
        tax_list=[tax],
        tax_doc_ids=["tax-1"],
    )
    codes = [i.code for i in issues]
    assert "DECLARED_INCOME_VS_DEPOSITS" in codes


def test_declared_income_close_to_deposits_passes() -> None:
    stmt = _stmt(credits=Decimal("150000"))  # ~RM 1.83M annualised
    tax = _tax(income=Decimal("1800000"))  # ~ same
    issues = run_cross_doc_checks(
        [stmt], ["bank-1"], [], [], tax_list=[tax], tax_doc_ids=["tax-1"]
    )
    assert not any(i.code == "DECLARED_INCOME_VS_DEPOSITS" for i in issues)


def test_audited_revenue_vs_tax_mismatch() -> None:
    fin = _fin(revenue=Decimal("2000000"))
    tax = _tax(income=Decimal("1000000"))  # 50% gap
    issues = run_cross_doc_checks(
        [],
        [],
        [],
        [],
        fin_list=[fin],
        fin_doc_ids=["fin-1"],
        tax_list=[tax],
        tax_doc_ids=["tax-1"],
    )
    assert any(i.code == "AUDITED_VS_TAX_REVENUE" for i in issues)


def test_financials_company_does_not_match_ssm() -> None:
    fin = _fin(company="BETA CORP SDN BHD")
    ssm = _ssm(name="ACME TRADING SDN BHD")
    issues = run_cross_doc_checks(
        [],
        [],
        [ssm],
        ["ssm-1"],
        fin_list=[fin],
        fin_doc_ids=["fin-1"],
    )
    mismatch = [i for i in issues if i.code == "FINANCIALS_SSM_MISMATCH"]
    assert mismatch and mismatch[0].severity is Severity.CRITICAL
