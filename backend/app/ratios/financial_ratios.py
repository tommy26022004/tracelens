"""Standard credit-assessment financial ratios.

Computable only when audited financials are present. The companion
module `bank_statement_metrics` handles bank-statement-only signals.

Each ratio carries an `interpretation` band so the agent's 5C prompt
gets a normalised view it can reason over without having to know
financial-ratio thresholds.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from app.ingestion.types import AuditedFinancials, FinancialPeriod


class RatioBand(str, Enum):
    HEALTHY = "healthy"
    ACCEPTABLE = "acceptable"
    STRETCHED = "stretched"
    DISTRESSED = "distressed"
    INSUFFICIENT_DATA = "insufficient_data"


class Ratio(BaseModel):
    name: str
    value: Decimal | None
    band: RatioBand
    formula: str = Field(description="Plain-English formula for the audit trail")
    explanation: str = Field(description="What this ratio means for credit decisions")


class FinancialRatios(BaseModel):
    document_id: str
    period_end: str
    current_ratio: Ratio
    debt_to_equity: Ratio
    net_profit_margin: Ratio
    interest_coverage: Ratio
    dsr: Ratio = Field(description="Debt Service Ratio against assumed annual debt service")


def _safe_div(a: Decimal, b: Decimal) -> Decimal | None:
    if b == 0:
        return None
    return (a / b).quantize(Decimal("0.0001"))


def _current_ratio(period: FinancialPeriod) -> Ratio:
    value = _safe_div(period.current_assets, period.current_liabilities)
    band = RatioBand.INSUFFICIENT_DATA
    if value is not None:
        if value >= Decimal("1.5"):
            band = RatioBand.HEALTHY
        elif value >= Decimal("1.0"):
            band = RatioBand.ACCEPTABLE
        elif value >= Decimal("0.75"):
            band = RatioBand.STRETCHED
        else:
            band = RatioBand.DISTRESSED
    return Ratio(
        name="Current Ratio",
        value=value,
        band=band,
        formula="current_assets / current_liabilities",
        explanation=(
            "Liquidity proxy. Values above 1.5 suggest the business can comfortably "
            "meet short-term obligations; below 1.0 raises liquidity risk."
        ),
    )


def _debt_to_equity(period: FinancialPeriod) -> Ratio:
    total_debt = period.current_liabilities + period.non_current_liabilities
    value = _safe_div(total_debt, period.total_equity)
    band = RatioBand.INSUFFICIENT_DATA
    if value is not None:
        if value <= Decimal("1.0"):
            band = RatioBand.HEALTHY
        elif value <= Decimal("2.0"):
            band = RatioBand.ACCEPTABLE
        elif value <= Decimal("3.0"):
            band = RatioBand.STRETCHED
        else:
            band = RatioBand.DISTRESSED
    return Ratio(
        name="Debt-to-Equity",
        value=value,
        band=band,
        formula="(current_liabilities + non_current_liabilities) / total_equity",
        explanation=(
            "Leverage proxy. Lower is safer. SME lenders typically tolerate up to 2:1 "
            "before requiring additional security."
        ),
    )


def _net_profit_margin(period: FinancialPeriod) -> Ratio:
    value = _safe_div(period.net_profit, period.revenue)
    band = RatioBand.INSUFFICIENT_DATA
    if value is not None:
        if value >= Decimal("0.10"):
            band = RatioBand.HEALTHY
        elif value >= Decimal("0.05"):
            band = RatioBand.ACCEPTABLE
        elif value >= Decimal("0.00"):
            band = RatioBand.STRETCHED
        else:
            band = RatioBand.DISTRESSED
    return Ratio(
        name="Net Profit Margin",
        value=value,
        band=band,
        formula="net_profit / revenue",
        explanation=(
            "Profitability proxy. Negative margins indicate the business is losing "
            "money on its core operations."
        ),
    )


def _interest_coverage(period: FinancialPeriod) -> Ratio:
    if period.interest_expense == 0:
        return Ratio(
            name="Interest Coverage",
            value=None,
            band=RatioBand.HEALTHY,
            formula="EBIT / interest_expense",
            explanation="No interest expense — coverage is trivially adequate.",
        )
    value = _safe_div(period.ebit, period.interest_expense)
    band = RatioBand.INSUFFICIENT_DATA
    if value is not None:
        if value >= Decimal("4.0"):
            band = RatioBand.HEALTHY
        elif value >= Decimal("2.0"):
            band = RatioBand.ACCEPTABLE
        elif value >= Decimal("1.5"):
            band = RatioBand.STRETCHED
        else:
            band = RatioBand.DISTRESSED
    return Ratio(
        name="Interest Coverage",
        value=value,
        band=band,
        formula="EBIT / interest_expense",
        explanation=(
            "How many times current EBIT covers interest. Below 1.5× signals the "
            "business cannot service existing debt out of operating earnings."
        ),
    )


def _dsr(period: FinancialPeriod) -> Ratio:
    """Debt Service Ratio.

    Real DSR requires the proposed loan's debt-service schedule. We
    estimate annual debt service as `interest_expense + 10% of total
    debt` (a common SME amortisation proxy). This gives the loan
    officer an initial signal; the dashboard's `recommended_human_checks`
    list will tell them to refine with actual amortisation terms.
    """
    estimated_principal_repayment = (
        period.current_liabilities + period.non_current_liabilities
    ) * Decimal("0.10")
    annual_debt_service = period.interest_expense + estimated_principal_repayment
    value = _safe_div(period.cash_from_operations, annual_debt_service)
    band = RatioBand.INSUFFICIENT_DATA
    if value is not None:
        if value >= Decimal("1.5"):
            band = RatioBand.HEALTHY
        elif value >= Decimal("1.2"):
            band = RatioBand.ACCEPTABLE
        elif value >= Decimal("1.0"):
            band = RatioBand.STRETCHED
        else:
            band = RatioBand.DISTRESSED
    return Ratio(
        name="Debt Service Ratio (est.)",
        value=value,
        band=band,
        formula="cash_from_operations / (interest_expense + 10% × total_debt)",
        explanation=(
            "Estimated cash-flow coverage of debt service. <1.0 means operations "
            "alone cannot cover assumed servicing; needs refinement against "
            "the proposed loan's actual amortisation schedule."
        ),
    )


def compute_financial_ratios(fin: AuditedFinancials, document_id: str) -> FinancialRatios:
    """Always uses the most recent period (`fin.periods[0]`)."""
    period = fin.periods[0]
    return FinancialRatios(
        document_id=document_id,
        period_end=period.period_end.isoformat(),
        current_ratio=_current_ratio(period),
        debt_to_equity=_debt_to_equity(period),
        net_profit_margin=_net_profit_margin(period),
        interest_coverage=_interest_coverage(period),
        dsr=_dsr(period),
    )
