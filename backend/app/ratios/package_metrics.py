"""Account-aware cash-flow aggregation and multi-year trend metrics."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal
from itertools import pairwise

from pydantic import BaseModel

from app.ingestion.coherent_financials import money
from app.ingestion.types import AuditedFinancials, BankStatement


def _month_end(value: date) -> date:
    return date(value.year, value.month, calendar.monthrange(value.year, value.month)[1])


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def allocate_amount_by_month(
    period_start: date,
    period_end: date,
    amount: Decimal,
) -> dict[str, Decimal]:
    total_days = (period_end - period_start).days + 1
    if total_days <= 0:
        return {}
    allocations: dict[str, Decimal] = {}
    cursor = date(period_start.year, period_start.month, 1)
    while cursor <= period_end:
        overlap_start = max(period_start, cursor)
        overlap_end = min(period_end, _month_end(cursor))
        overlap_days = (overlap_end - overlap_start).days + 1
        allocations[f"{cursor.year}-{cursor.month:02d}"] = money(
            amount * Decimal(overlap_days) / Decimal(total_days)
        )
        cursor = _next_month(cursor)
    if allocations:
        final_key = next(reversed(allocations))
        allocations[final_key] = money(
            allocations[final_key] + amount - sum(allocations.values(), Decimal(0))
        )
    return allocations


def unique_bank_statements(statements: list[BankStatement]) -> list[BankStatement]:
    seen: set[tuple[object, ...]] = set()
    unique: list[BankStatement] = []
    for statement in statements:
        fingerprint = (
            statement.account_number,
            statement.statement_period_start,
            statement.statement_period_end,
            statement.opening_balance,
            statement.closing_balance,
            statement.total_credits,
            statement.total_debits,
        )
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(statement)
    return unique


def aggregate_monthly_amounts(
    statements: list[BankStatement],
    field: str,
) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for statement in unique_bank_statements(statements):
        amount = getattr(statement, field)
        for month, allocated in allocate_amount_by_month(
            statement.statement_period_start, statement.statement_period_end, amount
        ).items():
            totals[month] += allocated
    return {month: money(value) for month, value in sorted(totals.items())}


class PackageCashFlowMetrics(BaseModel):
    statement_count: int
    account_count: int
    covered_months: list[str]
    monthly_credits: dict[str, Decimal]
    monthly_debits: dict[str, Decimal]
    annualised_credits_by_year: dict[int, Decimal]
    net_cash_change: Decimal


def compute_package_cash_flow(statements: list[BankStatement]) -> PackageCashFlowMetrics:
    unique = unique_bank_statements(statements)
    monthly_credits = aggregate_monthly_amounts(unique, "total_credits")
    monthly_debits = aggregate_monthly_amounts(unique, "total_debits")
    annualised: dict[int, Decimal] = {}
    years = sorted({int(month[:4]) for month in monthly_credits})
    for year in years:
        values = [value for month, value in monthly_credits.items() if int(month[:4]) == year]
        annualised[year] = money(sum(values, Decimal(0)) * Decimal(12) / Decimal(len(values)))
    return PackageCashFlowMetrics(
        statement_count=len(unique),
        account_count=len({statement.account_number for statement in unique}),
        covered_months=sorted(monthly_credits),
        monthly_credits=monthly_credits,
        monthly_debits=monthly_debits,
        annualised_credits_by_year=annualised,
        net_cash_change=money(
            sum(monthly_credits.values(), Decimal(0)) - sum(monthly_debits.values(), Decimal(0))
        ),
    )


class FinancialTrendMetrics(BaseModel):
    years: list[int]
    revenue_by_year: dict[int, Decimal]
    net_profit_by_year: dict[int, Decimal]
    revenue_growth_rates: dict[int, Decimal]
    revenue_cagr: Decimal | None


def compute_financial_trend(financials: list[AuditedFinancials]) -> FinancialTrendMetrics:
    current_periods = {}
    for item in sorted(financials, key=lambda item: item.financial_year_end):
        for period in item.periods:
            current_periods[period.period_end.year] = period
    years = sorted(current_periods)
    revenue = {year: current_periods[year].revenue for year in years}
    net_profit = {year: current_periods[year].net_profit for year in years}
    growth: dict[int, Decimal] = {}
    for previous, current in pairwise(years):
        previous_revenue = revenue[previous]
        if previous_revenue:
            growth[current] = money(
                (revenue[current] - previous_revenue) / previous_revenue * Decimal(100)
            )
    cagr: Decimal | None = None
    if len(years) >= 2 and revenue[years[0]] > 0:
        periods = years[-1] - years[0]
        cagr = money(
            (Decimal(float(revenue[years[-1]] / revenue[years[0]]) ** (1 / periods)) - 1)
            * Decimal(100)
        )
    return FinancialTrendMetrics(
        years=years,
        revenue_by_year=revenue,
        net_profit_by_year=net_profit,
        revenue_growth_rates=growth,
        revenue_cagr=cagr,
    )
