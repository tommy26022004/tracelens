"""Optional integration test that hits a live Qdrant instance.

Skipped unless `FYP_RUN_INTEGRATION=1`. Mirrors `scripts/smoke_ingest.py`
in assertion form so the same coverage runs in pytest when desired.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.ingestion.pipeline import ingest_bank_statement
from app.ingestion.store import COLLECTION_NAME, VectorStore
from app.ingestion.synthetic import GeneratorConfig, generate

pytestmark = pytest.mark.skipif(
    os.environ.get("FYP_RUN_INTEGRATION") != "1",
    reason="Integration test — set FYP_RUN_INTEGRATION=1 with Qdrant running",
)


def test_ingest_and_search_against_real_qdrant(tmp_path: Path) -> None:
    pdf, _ = generate(GeneratorConfig(seed=123, n_transactions=15), tmp_path)
    store = VectorStore()
    if store._client.collection_exists(COLLECTION_NAME):  # noqa: SLF001
        store._client.delete_collection(COLLECTION_NAME)  # noqa: SLF001

    result, statement = ingest_bank_statement(pdf, document_id="pytest-doc", store=store)

    assert result.chunks_upserted == 1 + len(statement.transactions)
    hits = store.semantic_search("opening and closing balance", limit=3, document_id="pytest-doc")
    assert hits, "Expected at least one hit from semantic search"
    assert {h.kind for h in hits} <= {"summary", "transaction"}

    last_chunk_id = f"pytest-doc:transaction:{len(statement.transactions) - 1}"
    exact = store.get_chunk(last_chunk_id)
    assert exact is not None
    assert exact.chunk_id == last_chunk_id
    assert exact.document_id == "pytest-doc"
