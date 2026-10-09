"""Chunking for vector storage.

Bank statements are highly structured, so we chunk along their natural
grain instead of using a generic sliding window:

- One **summary chunk** per statement: bank, holder, period, totals.
- One **transaction chunk** per row: date, description, amount, balance.

Each chunk carries `source_metadata` so that any retrieval result can be
cited back to a precise (document_id, page, row_index) — the FEATERS
explainability requirement for the agent's outputs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.ingestion.parser import ParsedPage
from app.ingestion.types import (
    AuditedFinancials,
    BankStatement,
    SourceLocation,
    SSMRegistration,
    TaxReturn,
    Transaction,
)


class Chunk(BaseModel):
    """One unit of text destined for the vector store."""

    chunk_id: str = Field(description="Stable id: {document_id}:{kind}:{index}")
    document_id: str
    kind: str  # "summary" | "transaction"
    text: str
    page: int | None
    source_metadata: dict[str, Any]


def _attach_sources(chunk: Chunk, fields: dict[str, SourceLocation]) -> Chunk:
    locations = [
        {"field": field, **location.model_dump(mode="json")} for field, location in fields.items()
    ]
    pages = sorted({location.page for location in fields.values()})
    chunk.page = pages[0] if pages else None
    chunk.source_metadata.update(
        source_pages=pages, source_locations=locations, source_verified=bool(locations)
    )
    return chunk


def _summary_text(stmt: BankStatement) -> str:
    return (
        f"Bank statement summary. "
        f"Bank: {stmt.bank_name}. Account holder: {stmt.account_holder}. "
        f"Account number: {stmt.account_number}. "
        f"Period: {stmt.statement_period_start.isoformat()} to "
        f"{stmt.statement_period_end.isoformat()}. "
        f"Opening balance: {stmt.opening_balance}. "
        f"Closing balance: {stmt.closing_balance}. "
        f"Total credits: {stmt.total_credits}. "
        f"Total debits: {stmt.total_debits}. "
        f"Transactions: {len(stmt.transactions)}."
    )


def _transaction_text(txn: Transaction) -> str:
    side = "credit" if txn.credit is not None else "debit"
    amount = txn.credit if txn.credit is not None else txn.debit
    return (
        f"{txn.txn_date.isoformat()} | {side} | RM {amount} | "
        f"balance RM {txn.balance} | {txn.description}"
    )


def chunk_bank_statement(stmt: BankStatement, document_id: str) -> list[Chunk]:
    """Split a `BankStatement` into citation-preserving chunks."""
    chunks: list[Chunk] = [
        Chunk(
            chunk_id=f"{document_id}:summary:0",
            document_id=document_id,
            kind="summary",
            text=_summary_text(stmt),
            page=1,
            source_metadata={
                "bank_name": stmt.bank_name,
                "account_holder": stmt.account_holder,
                "account_number": stmt.account_number,
                "period_start": stmt.statement_period_start.isoformat(),
                "period_end": stmt.statement_period_end.isoformat(),
                "opening_balance": str(stmt.opening_balance),
                "closing_balance": str(stmt.closing_balance),
                "total_credits": str(stmt.total_credits),
                "total_debits": str(stmt.total_debits),
            },
        )
    ]

    for idx, txn in enumerate(stmt.transactions):
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}:transaction:{idx}",
                document_id=document_id,
                kind="transaction",
                text=_transaction_text(txn),
                page=txn.page,
                source_metadata={
                    "txn_date": txn.txn_date.isoformat(),
                    "description": txn.description,
                    "debit": str(txn.debit) if txn.debit is not None else None,
                    "credit": str(txn.credit) if txn.credit is not None else None,
                    "balance": str(txn.balance),
                    "row_index": idx,
                },
            )
        )

    _attach_sources(
        chunks[0],
        {
            **stmt.source_fields,
            **{
                f"transaction_{index}": transaction.source
                for index, transaction in enumerate(stmt.transactions)
                if transaction.source is not None
            },
        },
    )
    for chunk, transaction in zip(chunks[1:], stmt.transactions, strict=True):
        if transaction.source is not None:
            _attach_sources(chunk, {"transaction": transaction.source})
    return chunks


def _ssm_summary_text(ssm: SSMRegistration) -> str:
    return (
        f"SSM registration. "
        f"Company: {ssm.company_name} ({ssm.registration_number}). "
        f"Type: {ssm.company_type}. "
        f"Incorporated: {ssm.incorporation_date.isoformat()}. "
        f"Paid-up capital: RM {ssm.paid_up_capital}. "
        f"Address: {ssm.business_address}. "
        f"Directors: {len(ssm.directors)}."
    )


def _director_text(director, idx: int) -> str:
    return (
        f"Director #{idx + 1}: {director.name}. "
        f"NRIC/Passport: {director.nric_or_passport or '-'}. "
        f"Role: {director.role or '-'}."
    )


def chunk_ssm_registration(ssm: SSMRegistration, document_id: str) -> list[Chunk]:
    """Citation-preserving chunks for an SSM Form 9 document."""
    chunks: list[Chunk] = [
        Chunk(
            chunk_id=f"{document_id}:summary:0",
            document_id=document_id,
            kind="summary",
            text=_ssm_summary_text(ssm),
            page=1,
            source_metadata={
                "company_name": ssm.company_name,
                "registration_number": ssm.registration_number,
                "incorporation_date": ssm.incorporation_date.isoformat(),
                "company_type": ssm.company_type,
                "business_address": ssm.business_address,
                "paid_up_capital": str(ssm.paid_up_capital),
                "director_count": len(ssm.directors),
            },
        )
    ]

    for idx, director in enumerate(ssm.directors):
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}:director:{idx}",
                document_id=document_id,
                kind="director",
                text=_director_text(director, idx),
                page=1,
                source_metadata={
                    "name": director.name,
                    "nric_or_passport": director.nric_or_passport,
                    "role": director.role,
                    "row_index": idx,
                },
            )
        )

    _attach_sources(chunks[0], ssm.source_fields)
    for chunk, director in zip(chunks[1:], ssm.directors, strict=True):
        _attach_sources(chunk, {"director": director.source} if director.source else {})
    return chunks


def _financials_summary_text(fin: AuditedFinancials) -> str:
    current = fin.periods[0]
    return (
        f"Audited financials summary. "
        f"Company: {fin.company_name}. Auditor: {fin.auditor}. "
        f"FY end: {fin.financial_year_end.isoformat()}. "
        f"Source display unit: {fin.display_unit}; values normalized to "
        f"{fin.canonical_unit} using multiplier {fin.unit_multiplier}. "
        f"Revenue (current): RM {current.revenue}. "
        f"Net profit (current): RM {current.net_profit}. "
        f"Total equity: RM {current.total_equity}. "
        f"Periods reported: {len(fin.periods)}."
    )


def _period_text(period, idx: int) -> str:
    return (
        f"Period {period.period_end.isoformat()}: "
        f"revenue RM {period.revenue}, gross profit RM {period.gross_profit}, "
        f"EBIT RM {period.ebit}, net profit RM {period.net_profit}, "
        f"current assets RM {period.current_assets}, "
        f"current liabilities RM {period.current_liabilities}, "
        f"total equity RM {period.total_equity}, "
        f"cash from ops RM {period.cash_from_operations}."
    )


def chunk_audited_financials(fin: AuditedFinancials, document_id: str) -> list[Chunk]:
    chunks: list[Chunk] = [
        Chunk(
            chunk_id=f"{document_id}:summary:0",
            document_id=document_id,
            kind="summary",
            text=_financials_summary_text(fin),
            page=1,
            source_metadata={
                "company_name": fin.company_name,
                "auditor": fin.auditor,
                "financial_year_end": fin.financial_year_end.isoformat(),
                "period_count": len(fin.periods),
                "source_display_unit": fin.display_unit,
                "canonical_unit": fin.canonical_unit,
                "unit_multiplier": str(fin.unit_multiplier),
            },
        )
    ]
    for idx, period in enumerate(fin.periods):
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}:period:{idx}",
                document_id=document_id,
                kind="period",
                text=_period_text(period, idx),
                page=1 if idx == 0 else 2,
                source_metadata={
                    "period_end": period.period_end.isoformat(),
                    "source_display_unit": fin.display_unit,
                    "canonical_unit": fin.canonical_unit,
                    "unit_multiplier": str(fin.unit_multiplier),
                    "revenue": str(period.revenue),
                    "net_profit": str(period.net_profit),
                    "ebit": str(period.ebit),
                    "total_equity": str(period.total_equity),
                    "interest_expense": str(period.interest_expense),
                    "cash_from_operations": str(period.cash_from_operations),
                    "current_assets": str(period.current_assets),
                    "current_liabilities": str(period.current_liabilities),
                    "non_current_liabilities": str(period.non_current_liabilities),
                },
            )
        )
    _attach_sources(chunks[0], {**fin.source_fields, **fin.periods[0].source_fields})
    for chunk, period in zip(chunks[1:], fin.periods, strict=True):
        _attach_sources(chunk, period.source_fields)
    return chunks


def _tax_summary_text(tax: TaxReturn) -> str:
    return (
        f"Tax return summary. Company: {tax.company_name}. "
        f"Tax reference: {tax.tax_reference_number}. "
        f"Year of assessment: {tax.year_of_assessment}. "
        f"Gross business income: RM {tax.gross_business_income}. "
        f"Chargeable income: RM {tax.chargeable_income}. "
        f"Tax payable: RM {tax.tax_payable}."
    )


def chunk_tax_return(tax: TaxReturn, document_id: str) -> list[Chunk]:
    return [
        _attach_sources(
            Chunk(
                chunk_id=f"{document_id}:summary:0",
                document_id=document_id,
                kind="summary",
                text=_tax_summary_text(tax),
                page=1,
                source_metadata={
                    "company_name": tax.company_name,
                    "tax_reference_number": tax.tax_reference_number,
                    "year_of_assessment": tax.year_of_assessment,
                    "gross_business_income": str(tax.gross_business_income),
                    "chargeable_income": str(tax.chargeable_income),
                    "tax_payable": str(tax.tax_payable),
                },
            ),
            tax.source_fields,
        )
    ]


def chunk_unstructured_pages(
    pages: list[ParsedPage], document_id: str, document_kind: str
) -> list[Chunk]:
    return [
        Chunk(
            chunk_id=f"{document_id}:page:{page.page - 1}",
            document_id=document_id,
            kind="page",
            text=page.text,
            page=page.page,
            source_metadata={"document_kind": document_kind, "page": page.page},
        )
        for page in pages
    ]
