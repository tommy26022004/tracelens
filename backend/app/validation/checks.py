"""Deterministic validation checks over `BankStatement` data.

Each check returns zero or more `Inconsistency` records. An inconsistency
always carries:
- `code` — short stable identifier the dashboard can route on,
- `severity` — info / warning / critical, drives loan-officer prioritisation,
- `message` — human-readable explanation in plain English,
- `citations` — chunk_ids that an auditor can resolve to specific PDF
  rows. This is the FEATERS source-traceability requirement.

Cross-document validation (declared revenue vs deposits, tax declared
income vs financials) will be added once additional document types
arrive in Phase 4+. The shape of `Inconsistency` is already prepared
for it.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from app.ingestion.types import BankStatement


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Inconsistency(BaseModel):
    code: str
    severity: Severity
    message: str
    citations: list[str] = Field(
        default_factory=list,
        description="chunk_ids of the underlying source rows",
    )


def _chunk_id(document_id: str, kind: str, index: int) -> str:
    return f"{document_id}:{kind}:{index}"


def _check_balance_arithmetic(stmt: BankStatement, document_id: str) -> list[Inconsistency]:
    """opening + credits − debits == closing (within RM 0.01)."""
    expected = stmt.opening_balance + stmt.total_credits - stmt.total_debits
    diff = (expected - stmt.closing_balance).copy_abs()
    if diff > Decimal("0.01"):
        return [
            Inconsistency(
                code="BALANCE_ARITHMETIC",
                severity=Severity.CRITICAL,
                message=(
                    f"Header arithmetic does not reconcile. "
                    f"opening({stmt.opening_balance}) + credits({stmt.total_credits}) "
                    f"− debits({stmt.total_debits}) = {expected}, "
                    f"but declared closing is {stmt.closing_balance} "
                    f"(diff {diff})."
                ),
                citations=[_chunk_id(document_id, "summary", 0)],
            )
        ]
    return []


def _check_running_balance(stmt: BankStatement, document_id: str) -> list[Inconsistency]:
    """Each row's `balance` must equal previous balance ± its own movement.

    Catches single-row OCR mistakes that the header totals would still hide.
    """
    issues: list[Inconsistency] = []
    running = stmt.opening_balance
    for idx, txn in enumerate(stmt.transactions):
        delta = (txn.credit or Decimal(0)) - (txn.debit or Decimal(0))
        expected = running + delta
        if (expected - txn.balance).copy_abs() > Decimal("0.01"):
            issues.append(
                Inconsistency(
                    code="RUNNING_BALANCE",
                    severity=Severity.CRITICAL,
                    message=(
                        f"Row {idx} balance {txn.balance} does not match "
                        f"running balance {expected} (prev {running} {'+' if delta >= 0 else ''}{delta})."
                    ),
                    citations=[_chunk_id(document_id, "transaction", idx)],
                )
            )
        running = txn.balance
    return issues


def _check_date_continuity(stmt: BankStatement, document_id: str) -> list[Inconsistency]:
    """Every transaction date must fall inside the declared statement period
    and the sequence must be non-decreasing."""
    issues: list[Inconsistency] = []
    prev_date = None
    for idx, txn in enumerate(stmt.transactions):
        if not (stmt.statement_period_start <= txn.txn_date <= stmt.statement_period_end):
            issues.append(
                Inconsistency(
                    code="DATE_OUTSIDE_PERIOD",
                    severity=Severity.WARNING,
                    message=(
                        f"Row {idx} date {txn.txn_date} is outside the statement "
                        f"period {stmt.statement_period_start}..{stmt.statement_period_end}."
                    ),
                    citations=[_chunk_id(document_id, "transaction", idx)],
                )
            )
        if prev_date is not None and txn.txn_date < prev_date:
            issues.append(
                Inconsistency(
                    code="DATE_OUT_OF_ORDER",
                    severity=Severity.WARNING,
                    message=(
                        f"Row {idx} date {txn.txn_date} precedes the previous "
                        f"row's date {prev_date}."
                    ),
                    citations=[_chunk_id(document_id, "transaction", idx)],
                )
            )
        prev_date = txn.txn_date
    return issues


def _check_duplicate_transactions(
    stmt: BankStatement, document_id: str
) -> list[Inconsistency]:
    """Same date + same amount + same description appearing twice within 24h
    is flagged for human review (could be legitimate batch payment or a
    duplicate entry — the loan officer decides)."""
    seen: dict[tuple, list[int]] = defaultdict(list)
    for idx, txn in enumerate(stmt.transactions):
        key = (txn.description, txn.debit, txn.credit)
        seen[key].append(idx)

    issues: list[Inconsistency] = []
    for (desc, debit, credit), indices in seen.items():
        if len(indices) < 2:
            continue
        # Check for any pair within 24h.
        sorted_idx = sorted(indices, key=lambda i: stmt.transactions[i].txn_date)
        for a, b in zip(sorted_idx, sorted_idx[1:], strict=False):
            gap = stmt.transactions[b].txn_date - stmt.transactions[a].txn_date
            if gap <= timedelta(days=1):
                amount = credit if credit is not None else debit
                issues.append(
                    Inconsistency(
                        code="POSSIBLE_DUPLICATE",
                        severity=Severity.INFO,
                        message=(
                            f"Rows {a} and {b}: identical entry "
                            f"'{desc}' for RM {amount} within {gap.days} day(s)."
                        ),
                        citations=[
                            _chunk_id(document_id, "transaction", a),
                            _chunk_id(document_id, "transaction", b),
                        ],
                    )
                )
    return issues


def run_checks(
    statements: list[BankStatement], document_ids: list[str]
) -> list[Inconsistency]:
    """Run every deterministic check against every statement.

    `statements` and `document_ids` must align by index — the order
    `extract_node` writes them is the order assumed here.
    """
    if len(statements) != len(document_ids):
        raise ValueError(
            f"statements ({len(statements)}) and document_ids "
            f"({len(document_ids)}) length mismatch"
        )

    issues: list[Inconsistency] = []
    for stmt, doc_id in zip(statements, document_ids, strict=True):
        issues.extend(_check_balance_arithmetic(stmt, doc_id))
        issues.extend(_check_running_balance(stmt, doc_id))
        issues.extend(_check_date_continuity(stmt, doc_id))
        issues.extend(_check_duplicate_transactions(stmt, doc_id))
    return issues
