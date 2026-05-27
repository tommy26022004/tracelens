"""Financial ratio band classification tests.

Uses hand-crafted FinancialPeriod fixtures so each band is exercised
without depending on the synthetic generator's randomness.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.ingestion.types import AuditedFinancials, FinancialPeriod
from app.ratios.financial_ratios import RatioBand, compute_financial_ratios


def _period(**overrides) -> FinancialPeriod:
    defaults = dict(
        period_end=date(2025, 12, 31),
        revenue=Decimal("1000000.00"),
        cost_of_sales=Decimal("600000.00"),
        gross_profit=Decimal("400000.00"),
        operating_expenses=Decimal("200000.00"),
        ebit=Decimal("200000.00"),
        interest_expense=Decimal("20000.00"),
        net_profit=Decimal("136800.00"),  # 13.68% margin → healthy
        current_assets=Decimal("300000.00"),
        non_current_assets=Decimal("500000.00"),
        current_liabilities=Decimal("150000.00"),  # current ratio 2.0 → healthy
        non_current_liabilities=Decimal("200000.00"),  # D/E (350k / 450k) ≈ 0.78 → healthy
        total_equity=Decimal("450000.00"),
        cash_from_operations=Decimal("180000.00"),
    )
    defaults.update(overrides)
    return FinancialPeriod(**defaults)


def _fin(period: FinancialPeriod) -> AuditedFinancials:
    return AuditedFinancials(
        company_name="ACME TRADING SDN BHD",
        auditor="Synthetic Audit",
        financial_year_end=period.period_end,
        periods=[period],
        page_count=1,
    )


def test_healthy_company_all_bands() -> None:
    r = compute_financial_ratios(_fin(_period()), document_id="doc-1")
    assert r.current_ratio.band is RatioBand.HEALTHY
    assert r.debt_to_equity.band is RatioBand.HEALTHY
    assert r.net_profit_margin.band is RatioBand.HEALTHY
    assert r.interest_coverage.band is RatioBand.HEALTHY
    assert r.dsr.band in (RatioBand.HEALTHY, RatioBand.ACCEPTABLE)


def test_distressed_company_flags_all_bands() -> None:
    period = _period(
        net_profit=Decimal("-50000.00"),  # negative margin
        ebit=Decimal("10000.00"),  # ICR 0.5 → distressed
        interest_expense=Decimal("20000.00"),
        current_assets=Decimal("100000.00"),
        current_liabilities=Decimal("200000.00"),  # current 0.5 → distressed
        non_current_liabilities=Decimal("600000.00"),
        total_equity=Decimal("100000.00"),  # D/E 8.0 → distressed
        cash_from_operations=Decimal("5000.00"),  # DSR << 1
    )
    r = compute_financial_ratios(_fin(period), document_id="doc-2")
    assert r.net_profit_margin.band is RatioBand.DISTRESSED
    assert r.interest_coverage.band is RatioBand.DISTRESSED
    assert r.current_ratio.band is RatioBand.DISTRESSED
    assert r.debt_to_equity.band is RatioBand.DISTRESSED
    assert r.dsr.band is RatioBand.DISTRESSED


def test_zero_interest_means_coverage_healthy() -> None:
    period = _period(interest_expense=Decimal("0.00"))
    r = compute_financial_ratios(_fin(period), document_id="doc-3")
    assert r.interest_coverage.band is RatioBand.HEALTHY
    assert r.interest_coverage.value is None  # signals "n/a — no interest"


def test_ratios_carry_formula_and_explanation() -> None:
    r = compute_financial_ratios(_fin(_period()), document_id="doc-4")
    for ratio in (r.current_ratio, r.debt_to_equity, r.net_profit_margin, r.interest_coverage, r.dsr):
        assert ratio.formula  # non-empty
        assert ratio.explanation
