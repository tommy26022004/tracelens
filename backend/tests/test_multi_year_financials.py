"""End-to-end coherence tests for multi-year, multi-account data."""

from __future__ import annotations

from decimal import Decimal

from app.ingestion.multi_year_financials import (
    MultiYearCoherentFinancials,
    build_default_multi_year_financials,
)


def test_multi_year_profile_round_trip_and_accounting_equations() -> None:
    profile = build_default_multi_year_financials()
    restored = MultiYearCoherentFinancials.model_validate_json(profile.model_dump_json())

    assert [snapshot.year for snapshot in restored.years] == [2023, 2024, 2025]
    assert len(restored.accounts) == 2
    assert all(snapshot.accounting_equation_delta == 0 for snapshot in restored.years)


def test_monthly_allocations_reconcile_without_double_counting() -> None:
    profile = build_default_multi_year_financials()
    allocations = profile.monthly_credit_targets(2025)

    assert len(allocations) == 18
    assert sum(allocations.values(), Decimal(0)) == profile.snapshot(2025).tax_gross_business_income
    assert all(("operating_account", month) in allocations for month in range(1, 13))
    assert all(("collection_account", month) in allocations for month in range(7, 13))


def test_each_month_reconciles_to_one_twelfth_of_annual_revenue() -> None:
    profile = build_default_multi_year_financials()
    allocations = profile.monthly_credit_targets(2025)
    expected_monthly = profile.snapshot(2025).tax_gross_business_income / Decimal(12)

    for month in range(1, 13):
        month_total = sum(
            amount
            for (account_id, allocation_month), amount in allocations.items()
            if allocation_month == month and account_id
        )
        assert abs(month_total - expected_monthly) <= Decimal("0.01")
