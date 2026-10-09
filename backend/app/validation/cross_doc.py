"""Cross-document validation checks.

Single-document checks (running balance, date period, …) live in
`checks.py`. This module handles validations that span document types:

- Account holder name on bank statement vs registered company name on
  SSM Form 9 (mismatch flags potential identity / shell-company risk).
- Incorporation date plausibility against the earliest bank-statement
  transaction date.

The shape of `Inconsistency` (severity, citations, code) is reused so
the dashboard renders cross-doc findings the same way it renders
intra-doc ones.
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.ingestion.types import AuditedFinancials, BankStatement, SSMRegistration, TaxReturn
from app.ratios.package_metrics import compute_package_cash_flow
from app.validation.checks import Inconsistency, Severity

_COMPANY_SUFFIXES = (
    "SDN BHD",
    "SDN. BHD.",
    "BERHAD",
    "BHD",
    "ENTERPRISE",
    "TRADING",
    "RESOURCES",
    "HOLDINGS",
)


def _normalise_name(name: str) -> str:
    """Strip punctuation, suffixes, and casing to compare two names.

    Loan officers see "ACME TRADING SDN BHD" on SSM but the bank may
    print "ACME TRADING S/B" or "ACME TRADING". The normaliser keeps
    only the discriminating tokens.
    """
    upper = name.upper()
    # Replace common abbreviations.
    upper = re.sub(r"\bS/B\b", "SDN BHD", upper)
    upper = re.sub(r"\bSDN\.\s*BHD\.?", "SDN BHD", upper)
    # Drop punctuation.
    upper = re.sub(r"[^A-Z0-9\s]", " ", upper)
    upper = re.sub(r"\s+", " ", upper).strip()
    return upper


def _is_strong_match(a: str, b: str) -> bool:
    """True if the cores (after dropping common suffixes) are identical."""
    a_norm, b_norm = _normalise_name(a), _normalise_name(b)
    if a_norm == b_norm:
        return True
    for suffix in _COMPANY_SUFFIXES:
        a_norm = a_norm.removesuffix(suffix).strip()
        b_norm = b_norm.removesuffix(suffix).strip()
    return bool(a_norm) and a_norm == b_norm


def _check_holder_vs_ssm(
    statements: list[BankStatement],
    bank_doc_ids: list[str],
    ssm_list: list[SSMRegistration],
    ssm_doc_ids: list[str],
) -> list[Inconsistency]:
    """Each bank-statement holder name should match at least one SSM record."""
    if not statements or not ssm_list:
        return []

    issues: list[Inconsistency] = []
    for stmt, bank_doc_id in zip(statements, bank_doc_ids, strict=True):
        matched_doc_id: str | None = None
        for ssm, ssm_doc_id in zip(ssm_list, ssm_doc_ids, strict=True):
            if _is_strong_match(stmt.account_holder, ssm.company_name):
                matched_doc_id = ssm_doc_id
                break
        if matched_doc_id is None:
            ssm_names = ", ".join(s.company_name for s in ssm_list)
            issues.append(
                Inconsistency(
                    code="HOLDER_SSM_MISMATCH",
                    severity=Severity.CRITICAL,
                    message=(
                        f"Bank statement holder '{stmt.account_holder}' does not "
                        f"match any registered company name on the SSM form(s): "
                        f"{ssm_names}."
                    ),
                    citations=[
                        f"{bank_doc_id}:summary:0",
                        *(f"{d}:summary:0" for d in ssm_doc_ids),
                    ],
                )
            )
    return issues


def _check_incorporation_predates_activity(
    statements: list[BankStatement],
    bank_doc_ids: list[str],
    ssm_list: list[SSMRegistration],
    ssm_doc_ids: list[str],
) -> list[Inconsistency]:
    """An account cannot show activity before the company was incorporated."""
    if not statements or not ssm_list:
        return []

    # Pair each statement with its best-matching SSM by holder name.
    issues: list[Inconsistency] = []
    for stmt, bank_doc_id in zip(statements, bank_doc_ids, strict=True):
        match: tuple[SSMRegistration, str] | None = None
        for ssm, ssm_doc_id in zip(ssm_list, ssm_doc_ids, strict=True):
            if _is_strong_match(stmt.account_holder, ssm.company_name):
                match = (ssm, ssm_doc_id)
                break
        if match is None:
            continue  # the holder-mismatch check already covered this case
        ssm, ssm_doc_id = match
        if stmt.statement_period_start < ssm.incorporation_date:
            issues.append(
                Inconsistency(
                    code="ACTIVITY_BEFORE_INCORPORATION",
                    severity=Severity.WARNING,
                    message=(
                        f"Bank statement period starts {stmt.statement_period_start} "
                        f"but SSM incorporation date is {ssm.incorporation_date}. "
                        "Verify whether the account predates the company."
                    ),
                    citations=[
                        f"{bank_doc_id}:summary:0",
                        f"{ssm_doc_id}:summary:0",
                    ],
                )
            )
    return issues


def _check_declared_income_vs_deposits(
    statements: list[BankStatement],
    bank_doc_ids: list[str],
    tax_list: list[TaxReturn],
    tax_doc_ids: list[str],
) -> list[Inconsistency]:
    """Tax-declared gross income should be in the same ballpark as annualised
    bank credits. >30% gap is suspicious; the message reports the gap so the
    loan officer can decide if it's seasonality or under-declaration."""
    if not statements or not tax_list:
        return []

    package_metrics = compute_package_cash_flow(statements)
    if not package_metrics.annualised_credits_by_year:
        return []

    issues: list[Inconsistency] = []
    for tax, tax_doc_id in zip(tax_list, tax_doc_ids, strict=True):
        if tax.year_of_assessment in package_metrics.annualised_credits_by_year:
            comparison_year = tax.year_of_assessment
        elif len(package_metrics.annualised_credits_by_year) == 1 and len(tax_list) == 1:
            comparison_year = next(iter(package_metrics.annualised_credits_by_year))
        else:
            continue
        annualised = package_metrics.annualised_credits_by_year[comparison_year]
        declared = tax.gross_business_income
        if declared == 0:
            continue
        gap = abs(annualised - declared) / declared
        if gap > Decimal("0.30"):
            issues.append(
                Inconsistency(
                    code="DECLARED_INCOME_VS_DEPOSITS",
                    severity=Severity.WARNING,
                    message=(
                        f"Tax return declares gross business income RM {declared}, "
                        f"but annualised bank credits suggest RM {annualised} "
                        f"({gap * 100:.0f}% gap). Verify whether the gap reflects "
                        "non-business deposits, seasonality, or under-declaration."
                    ),
                    citations=[
                        f"{tax_doc_id}:summary:0",
                        *(
                            f"{document_id}:summary:0"
                            for statement, document_id in zip(statements, bank_doc_ids, strict=True)
                            if statement.statement_period_start.year
                            <= comparison_year
                            <= statement.statement_period_end.year
                        ),
                    ],
                )
            )
    return issues


def _check_declared_income_vs_audited_revenue(
    fin_list: list[AuditedFinancials],
    fin_doc_ids: list[str],
    tax_list: list[TaxReturn],
    tax_doc_ids: list[str],
) -> list[Inconsistency]:
    """Audited revenue and tax-declared gross income should reconcile within
    a small tolerance (the difference is typically just deductions). >10%
    delta is worth flagging."""
    if not fin_list or not tax_list:
        return []

    issues: list[Inconsistency] = []
    for tax, tax_doc_id in zip(tax_list, tax_doc_ids, strict=True):
        for fin, fin_doc_id in zip(fin_list, fin_doc_ids, strict=True):
            if fin.financial_year_end.year != tax.year_of_assessment:
                continue
            audited_revenue = fin.periods[0].revenue
            if audited_revenue == 0:
                continue
            delta = abs(audited_revenue - tax.gross_business_income) / audited_revenue
            if delta > Decimal("0.10"):
                issues.append(
                    Inconsistency(
                        code="AUDITED_VS_TAX_REVENUE",
                        severity=Severity.WARNING,
                        message=(
                            f"Audited revenue RM {audited_revenue} (FY{fin.financial_year_end.year}) "
                            f"differs from tax-declared gross income RM {tax.gross_business_income} "
                            f"by {delta * 100:.0f}%."
                        ),
                        citations=[
                            f"{fin_doc_id}:period:0",
                            f"{tax_doc_id}:summary:0",
                        ],
                    )
                )
    return issues


def _check_audited_company_vs_ssm(
    fin_list: list[AuditedFinancials],
    fin_doc_ids: list[str],
    ssm_list: list[SSMRegistration],
    ssm_doc_ids: list[str],
) -> list[Inconsistency]:
    """Audited statements should be for the same legal entity as SSM."""
    if not fin_list or not ssm_list:
        return []

    issues: list[Inconsistency] = []
    for fin, fin_doc_id in zip(fin_list, fin_doc_ids, strict=True):
        matched = any(_is_strong_match(fin.company_name, ssm.company_name) for ssm in ssm_list)
        if not matched:
            issues.append(
                Inconsistency(
                    code="FINANCIALS_SSM_MISMATCH",
                    severity=Severity.CRITICAL,
                    message=(
                        f"Audited financials report for '{fin.company_name}' but no SSM "
                        f"record matches. Possible incorrect document or wrong applicant."
                    ),
                    citations=[
                        f"{fin_doc_id}:summary:0",
                        *(f"{d}:summary:0" for d in ssm_doc_ids),
                    ],
                )
            )
    return issues


def run_cross_doc_checks(
    statements: list[BankStatement],
    bank_doc_ids: list[str],
    ssm_list: list[SSMRegistration],
    ssm_doc_ids: list[str],
    fin_list: list[AuditedFinancials] | None = None,
    fin_doc_ids: list[str] | None = None,
    tax_list: list[TaxReturn] | None = None,
    tax_doc_ids: list[str] | None = None,
) -> list[Inconsistency]:
    fin_list = fin_list or []
    fin_doc_ids = fin_doc_ids or []
    tax_list = tax_list or []
    tax_doc_ids = tax_doc_ids or []
    return [
        *_check_holder_vs_ssm(statements, bank_doc_ids, ssm_list, ssm_doc_ids),
        *_check_incorporation_predates_activity(statements, bank_doc_ids, ssm_list, ssm_doc_ids),
        *_check_declared_income_vs_deposits(statements, bank_doc_ids, tax_list, tax_doc_ids),
        *_check_declared_income_vs_audited_revenue(fin_list, fin_doc_ids, tax_list, tax_doc_ids),
        *_check_audited_company_vs_ssm(fin_list, fin_doc_ids, ssm_list, ssm_doc_ids),
    ]
