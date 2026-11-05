"""Measured retrieval baseline against isolated, real Qdrant."""

import os
import uuid

import pytest

from app.ingestion.chunker import Chunk
from app.ingestion.store import VectorStore

pytestmark = pytest.mark.skipif(
    os.environ.get("FYP_RUN_INTEGRATION") != "1",
    reason="Requires an isolated Qdrant instance",
)


def test_retrieval_relevance_and_application_isolation() -> None:
    store = VectorStore()
    application_id = f"retrieval-eval-{uuid.uuid4()}"
    other_id = f"retrieval-other-{uuid.uuid4()}"
    cases = [
        ("bank", "bank_statement", "opening balance closing balance total credits debits", "What are the bank statement opening and closing balances?"),
        ("ssm", "ssm_registration", "company registration number incorporation directors", "What is the company registration number?"),
        ("financial", "audited_financials", "audited revenue net profit current assets liabilities", "What are audited revenue and net profit?"),
        ("tax", "tax_return", "tax return chargeable income tax payable assessment year", "What are chargeable income and tax payable?"),
    ]
    chunks = [
        Chunk(
            chunk_id=f"{application_id}/{name}:summary:0",
            document_id=f"{application_id}/{name}",
            kind="summary",
            text=content,
            page=1,
            source_metadata={"application_id": application_id, "document_kind": kind},
        )
        for name, kind, content, _ in cases
    ]
    chunks.append(
        Chunk(
            chunk_id=f"{other_id}/tax:summary:0",
            document_id=f"{other_id}/tax",
            kind="summary",
            text=cases[-1][2],
            page=1,
            source_metadata={"application_id": other_id, "document_kind": "tax_return"},
        )
    )
    try:
        store.upsert_chunks(chunks)
        reciprocal_ranks = []
        hits_at_three = []
        precision_at_three = []
        for name, _, _, query in cases:
            expected = f"{application_id}/{name}:summary:0"
            hits = store.semantic_search(query, limit=3, application_id=application_id)
            assert all(hit.source_metadata["application_id"] == application_id for hit in hits)
            ranks = [index for index, hit in enumerate(hits, 1) if hit.chunk_id == expected]
            reciprocal_ranks.append(1 / ranks[0] if ranks else 0)
            hits_at_three.append(int(bool(ranks)))
            precision_at_three.append(int(bool(ranks)) / len(hits) if hits else 0)
        print({
            "queries": len(cases),
            "recall_at_3": sum(hits_at_three) / len(cases),
            "precision_at_3": sum(precision_at_three) / len(cases),
            "mrr": sum(reciprocal_ranks) / len(cases),
        })
        assert sum(reciprocal_ranks) / len(cases) >= 0.75, reciprocal_ranks
    finally:
        store.delete_application(application_id)
        store.delete_application(other_id)
