"""High-level ingestion orchestration.

Glues parse → extract → chunk → store into a single callable. This is
what HTTP endpoints and CLI scripts depend on; tests can substitute a
fake `VectorStore` to verify ingestion logic without Qdrant running.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from pydantic import BaseModel

from app.ingestion.chunker import chunk_bank_statement
from app.ingestion.extractor import extract_bank_statement
from app.ingestion.parser import parse_pdf
from app.ingestion.store import VectorStore
from app.ingestion.types import BankStatement


class IngestionResult(BaseModel):
    document_id: str
    bank_name: str
    transaction_count: int
    chunks_upserted: int
    needs_ocr_pages: list[int]


def ingest_bank_statement(
    pdf_path: Path,
    *,
    document_id: str | None = None,
    store: VectorStore | None = None,
) -> tuple[IngestionResult, BankStatement]:
    """Run the full Phase 2 pipeline for one bank-statement PDF."""
    document_id = document_id or str(uuid.uuid4())

    pages = parse_pdf(pdf_path)
    needs_ocr = [p.page for p in pages if p.needs_ocr]
    statement = extract_bank_statement(pages)
    chunks = chunk_bank_statement(statement, document_id)

    vector_store = store or VectorStore()
    upserted = vector_store.upsert_chunks(chunks)

    return (
        IngestionResult(
            document_id=document_id,
            bank_name=statement.bank_name,
            transaction_count=len(statement.transactions),
            chunks_upserted=upserted,
            needs_ocr_pages=needs_ocr,
        ),
        statement,
    )
