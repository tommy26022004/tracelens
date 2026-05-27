"""Unit tests for the evaluation module."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.agent.state import ReasoningStep
from app.evaluation.extraction_accuracy import (
    score_audited_financials,
    score_bank_statement,
    score_ssm_registration,
    score_tax_return,
)
from app.evaluation.faithfulness import score_faithfulness
from app.evaluation.sus import SUS_QUESTIONS, score_sus_responses
from app.explainability.summary import RiskSummary
from app.ingestion.types import (
    AuditedFinancials,
    BankStatement,
    Director,
    FinancialPeriod,
    SSMRegistration,
    TaxReturn,
    Transaction,
)


def _bank() -> BankStatement:
    return BankStatement(
        bank_name="A",
        account_holder="B",
        account_number="1",
        statement_period_start=date(2026, 1, 1),
        statement_period_end=date(2026, 1, 31),
        opening_balance=Decimal("100"),
        closing_balance=Decimal("150"),
        total_credits=Decimal("60"),
        total_debits=Decimal("10"),
        transactions=[
            Transaction(
                txn_date=date(2026, 1, 5),
                description="DEPOSIT",
                debit=None,
                credit=Decimal("60"),
                balance=Decimal("160"),
                page=1,
            ),
            Transaction(
                txn_date=date(2026, 1, 10),
                description="WITHDRAWAL",
                debit=Decimal("10"),
                credit=None,
                balance=Decimal("150"),
                page=1,
            ),
        ],
    )


def test_bank_statement_perfect_match_yields_100pct() -> None:
    stmt = _bank()
    report = score_bank_statement(stmt, stmt)
    assert report.accuracy == 1.0
    assert report.mismatches == []


def test_bank_statement_single_wrong_field() -> None:
    expected = _bank()
    actual = expected.model_copy(update={"closing_balance": Decimal("999.00")})
    report = score_bank_statement(expected, actual)
    assert report.accuracy < 1.0
    assert any(m.field == "closing_balance" for m in report.mismatches)


def test_ssm_perfect_match() -> None:
    ssm = SSMRegistration(
        company_name="ACME SDN BHD",
        registration_number="x",
        incorporation_date=date(2024, 1, 1),
        company_type="SDN BHD",
        business_address="KL",
        paid_up_capital=Decimal("100"),
        directors=[Director(name="A", nric_or_passport="x", role="Director")],
    )
    report = score_ssm_registration(ssm, ssm)
    assert report.accuracy == 1.0


def test_audited_financials_field_mismatch() -> None:
    period = FinancialPeriod(
        period_end=date(2025, 12, 31),
        revenue=Decimal("1000"),
        cost_of_sales=Decimal("600"),
        gross_profit=Decimal("400"),
        operating_expenses=Decimal("100"),
        ebit=Decimal("300"),
        interest_expense=Decimal("20"),
        net_profit=Decimal("200"),
        current_assets=Decimal("300"),
        non_current_assets=Decimal("500"),
        current_liabilities=Decimal("150"),
        non_current_liabilities=Decimal("200"),
        total_equity=Decimal("450"),
        cash_from_operations=Decimal("180"),
    )
    fin = AuditedFinancials(
        company_name="ACME",
        auditor="Synthetic",
        financial_year_end=date(2025, 12, 31),
        periods=[period],
    )
    wrong = fin.model_copy(deep=True)
    wrong.periods[0].revenue = Decimal("999")
    report = score_audited_financials(fin, wrong)
    assert report.accuracy < 1.0


def test_tax_return_perfect_match() -> None:
    tax = TaxReturn(
        company_name="ACME",
        tax_reference_number="C 1",
        year_of_assessment=2025,
        gross_business_income=Decimal("100"),
        chargeable_income=Decimal("20"),
        tax_payable=Decimal("5"),
    )
    assert score_tax_return(tax, tax).accuracy == 1.0


def test_faithfulness_no_invalid_citations() -> None:
    allowed = ["doc-1:summary:0", "doc-1:transaction:0"]
    summary = RiskSummary(
        headline="Strong cash flow [doc-1:summary:0].",
        body="The applicant deposited consistently [doc-1:transaction:0].",
        recommended_human_checks=[],
        cited_chunk_ids=[],
    )
    report = score_faithfulness(summary, allowed)
    assert report.faithfulness == 1.0
    assert report.invalid_citations == []
    assert report.citations_total == 2


def test_faithfulness_catches_hallucinated_citation() -> None:
    allowed = ["doc-1:summary:0"]
    summary = RiskSummary(
        headline="Strong cash flow [doc-1:summary:0].",
        body="Deposit on Jan 5 [doc-1:transaction:999].",  # this chunk doesn't exist
        recommended_human_checks=[],
        cited_chunk_ids=[],
    )
    report = score_faithfulness(summary, allowed)
    assert report.faithfulness < 1.0
    assert "doc-1:transaction:999" in report.invalid_citations


def test_sus_perfect_positive_responses() -> None:
    """5 on positive, 1 on negative = best possible score (100)."""
    responses = [5, 1, 5, 1, 5, 1, 5, 1, 5, 1]
    result = score_sus_responses("user-1", responses)
    assert result.sus_score == 100.0
    assert result.band == "Excellent"


def test_sus_neutral_responses() -> None:
    responses = [3] * 10
    result = score_sus_responses("user-2", responses)
    assert result.sus_score == 50.0
    assert result.band == "OK"


def test_sus_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        score_sus_responses("user-3", [3] * 9 + [6])


def test_sus_rejects_wrong_length() -> None:
    with pytest.raises(ValueError):
        score_sus_responses("user-4", [3] * 9)


def test_sus_questions_exposed() -> None:
    assert len(SUS_QUESTIONS) == 10
    assert all(isinstance(q, str) for q in SUS_QUESTIONS)
