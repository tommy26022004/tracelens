"""Field-level extraction accuracy against ground-truth JSON.

We compare extracted Pydantic models against the ground truth produced
by the synthetic generators. Each field counts as one comparison; the
report breaks down right vs wrong so the loan officer (and the FYP
viva panel) can see which fields the extractor struggles with.

A 0.01 RM tolerance handles floating-point round-trips through ReportLab
rendering.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.ingestion.types import (
    AuditedFinancials,
    BankStatement,
    SSMRegistration,
    TaxReturn,
)

DEFAULT_TOLERANCE = Decimal("0.01")


class FieldComparison(BaseModel):
    field: str
    matched: bool
    expected: str | None = None
    actual: str | None = None


class ExtractionAccuracyReport(BaseModel):
    document_kind: str
    fields_total: int
    fields_matched: int
    accuracy: float
    mismatches: list[FieldComparison] = Field(default_factory=list)


def _eq(expected: Any, actual: Any, tolerance: Decimal = DEFAULT_TOLERANCE) -> bool:
    if isinstance(expected, Decimal) and isinstance(actual, Decimal):
        return abs(expected - actual) <= tolerance
    return expected == actual


def _compare_fields(
    expected_model: BaseModel,
    actual_model: BaseModel,
    fields: list[str],
) -> list[FieldComparison]:
    out: list[FieldComparison] = []
    for field in fields:
        exp = getattr(expected_model, field)
        act = getattr(actual_model, field)
        out.append(
            FieldComparison(
                field=field,
                matched=_eq(exp, act),
                expected=str(exp),
                actual=str(act),
            )
        )
    return out


def _build_report(kind: str, comparisons: list[FieldComparison]) -> ExtractionAccuracyReport:
    matched = sum(1 for c in comparisons if c.matched)
    total = len(comparisons)
    return ExtractionAccuracyReport(
        document_kind=kind,
        fields_total=total,
        fields_matched=matched,
        accuracy=matched / total if total > 0 else 1.0,
        mismatches=[c for c in comparisons if not c.matched],
    )


def score_bank_statement(
    expected: BankStatement, actual: BankStatement
) -> ExtractionAccuracyReport:
    """Header + per-transaction comparison. Description normalised to ignore
    whitespace differences (rendering artefacts)."""
    header_fields = [
        "bank_name", "account_holder", "account_number",
        "statement_period_start", "statement_period_end",
        "opening_balance", "closing_balance",
        "total_credits", "total_debits",
    ]
    comparisons = _compare_fields(expected, actual, header_fields)

    # Per-transaction fields.
    if len(expected.transactions) != len(actual.transactions):
        comparisons.append(
            FieldComparison(
                field="transaction_count",
                matched=False,
                expected=str(len(expected.transactions)),
                actual=str(len(actual.transactions)),
            )
        )
    for idx, (exp_t, act_t) in enumerate(
        zip(expected.transactions, actual.transactions, strict=False)
    ):
        for field in ("txn_date", "debit", "credit", "balance"):
            exp_v = getattr(exp_t, field)
            act_v = getattr(act_t, field)
            comparisons.append(
                FieldComparison(
                    field=f"transactions[{idx}].{field}",
                    matched=_eq(exp_v, act_v),
                    expected=str(exp_v),
                    actual=str(act_v),
                )
            )
        exp_desc = " ".join(exp_t.description.split())
        act_desc = " ".join(act_t.description.split())
        comparisons.append(
            FieldComparison(
                field=f"transactions[{idx}].description",
                matched=exp_desc == act_desc,
                expected=exp_desc,
                actual=act_desc,
            )
        )

    return _build_report("bank_statement", comparisons)


def score_ssm_registration(
    expected: SSMRegistration, actual: SSMRegistration
) -> ExtractionAccuracyReport:
    header_fields = [
        "company_name", "registration_number", "incorporation_date",
        "company_type", "business_address", "paid_up_capital",
    ]
    comparisons = _compare_fields(expected, actual, header_fields)
    comparisons.append(
        FieldComparison(
            field="director_count",
            matched=len(expected.directors) == len(actual.directors),
            expected=str(len(expected.directors)),
            actual=str(len(actual.directors)),
        )
    )
    for idx, (exp_d, act_d) in enumerate(
        zip(expected.directors, actual.directors, strict=False)
    ):
        for field in ("name", "nric_or_passport", "role"):
            comparisons.append(
                FieldComparison(
                    field=f"directors[{idx}].{field}",
                    matched=getattr(exp_d, field) == getattr(act_d, field),
                    expected=str(getattr(exp_d, field)),
                    actual=str(getattr(act_d, field)),
                )
            )
    return _build_report("ssm_registration", comparisons)


def score_audited_financials(
    expected: AuditedFinancials, actual: AuditedFinancials
) -> ExtractionAccuracyReport:
    header = ["company_name", "auditor", "financial_year_end"]
    comparisons = _compare_fields(expected, actual, header)
    comparisons.append(
        FieldComparison(
            field="period_count",
            matched=len(expected.periods) == len(actual.periods),
            expected=str(len(expected.periods)),
            actual=str(len(actual.periods)),
        )
    )
    period_fields = [
        "period_end", "revenue", "cost_of_sales", "gross_profit",
        "operating_expenses", "ebit", "interest_expense", "net_profit",
        "current_assets", "non_current_assets",
        "current_liabilities", "non_current_liabilities", "total_equity",
        "cash_from_operations",
    ]
    for idx, (exp_p, act_p) in enumerate(zip(expected.periods, actual.periods, strict=False)):
        comparisons.extend(
            FieldComparison(
                field=f"periods[{idx}].{f}",
                matched=_eq(getattr(exp_p, f), getattr(act_p, f)),
                expected=str(getattr(exp_p, f)),
                actual=str(getattr(act_p, f)),
            )
            for f in period_fields
        )
    return _build_report("audited_financials", comparisons)


def score_tax_return(expected: TaxReturn, actual: TaxReturn) -> ExtractionAccuracyReport:
    fields = [
        "company_name", "tax_reference_number", "year_of_assessment",
        "gross_business_income", "chargeable_income", "tax_payable",
    ]
    return _build_report("tax_return", _compare_fields(expected, actual, fields))
