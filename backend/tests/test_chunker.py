"""Chunking-level tests — no embeddings / Qdrant required."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.ingestion.chunker import chunk_bank_statement
from app.ingestion.types import BankStatement, Transaction


def _sample_statement() -> BankStatement:
    return BankStatement(
        bank_name="Synthetic Bank Berhad",
        account_holder="ACME TRADING SDN BHD",
        account_number="5141-2233-4455",
        statement_period_start=date(2026, 1, 1),
        statement_period_end=date(2026, 1, 31),
        opening_balance=Decimal("100.00"),
        closing_balance=Decimal("150.00"),
        total_credits=Decimal("60.00"),
        total_debits=Decimal("10.00"),
        transactions=[
            Transaction(
                txn_date=date(2026, 1, 5),
                description="FPX TRANSFER FROM MAYBANK",
                debit=None,
                credit=Decimal("60.00"),
                balance=Decimal("160.00"),
                page=1,
            ),
            Transaction(
                txn_date=date(2026, 1, 10),
                description="DUITNOW TRANSFER TO SUPPLIER",
                debit=Decimal("10.00"),
                credit=None,
                balance=Decimal("150.00"),
                page=1,
            ),
        ],
    )


def test_chunker_emits_one_summary_plus_one_per_transaction() -> None:
    stmt = _sample_statement()
    chunks = chunk_bank_statement(stmt, document_id="doc-1")

    assert len(chunks) == 1 + len(stmt.transactions)
    assert chunks[0].kind == "summary"
    assert all(c.kind == "transaction" for c in chunks[1:])


def test_chunk_ids_are_stable_and_unique() -> None:
    stmt = _sample_statement()
    chunks = chunk_bank_statement(stmt, document_id="doc-xyz")
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert chunks[0].chunk_id == "doc-xyz:summary:0"
    assert chunks[1].chunk_id == "doc-xyz:transaction:0"


def test_transaction_chunk_carries_citation_metadata() -> None:
    stmt = _sample_statement()
    chunks = chunk_bank_statement(stmt, document_id="d")
    credit_chunk = chunks[1]
    assert credit_chunk.page == 1
    assert credit_chunk.source_metadata["credit"] == "60.00"
    assert credit_chunk.source_metadata["debit"] is None
    assert credit_chunk.source_metadata["row_index"] == 0
