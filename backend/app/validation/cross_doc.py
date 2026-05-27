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

from app.ingestion.types import BankStatement, SSMRegistration
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


def run_cross_doc_checks(
    statements: list[BankStatement],
    bank_doc_ids: list[str],
    ssm_list: list[SSMRegistration],
    ssm_doc_ids: list[str],
) -> list[Inconsistency]:
    return [
        *_check_holder_vs_ssm(statements, bank_doc_ids, ssm_list, ssm_doc_ids),
        *_check_incorporation_predates_activity(
            statements, bank_doc_ids, ssm_list, ssm_doc_ids
        ),
    ]
