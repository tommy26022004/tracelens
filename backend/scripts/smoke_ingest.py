"""End-to-end smoke test for Phase 2.

Generates a synthetic statement, ingests it through the full pipeline
against a real Qdrant container, then runs three retrieval queries to
prove the store is searchable. Prints a one-line PASS/FAIL summary
suitable for CI later.

Run:
    python -m scripts.smoke_ingest

Requires:
- Qdrant reachable at QDRANT_URL (default http://localhost:6333)
- GEMINI_API_KEY optional — without it, deterministic stub embeddings
  are used (still exercises full code path).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from app.ingestion.pipeline import ingest_bank_statement
from app.ingestion.store import COLLECTION_NAME, VectorStore
from app.ingestion.synthetic import GeneratorConfig, generate


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        pdf, _ = generate(GeneratorConfig(seed=99, n_transactions=20), Path(tmp))
        store = VectorStore()

        # Wipe any prior run of the smoke test so counts are predictable.
        if store._client.collection_exists(COLLECTION_NAME):  # noqa: SLF001
            store._client.delete_collection(COLLECTION_NAME)  # noqa: SLF001

        result, statement = ingest_bank_statement(pdf, document_id="smoke-doc", store=store)
        print(f"Ingested document_id={result.document_id}")
        print(f"  bank          : {result.bank_name}")
        print(f"  transactions  : {result.transaction_count}")
        print(f"  chunks upserted: {result.chunks_upserted}")
        print(f"  needs_ocr     : {result.needs_ocr_pages}")

        expected_chunks = 1 + len(statement.transactions)
        if result.chunks_upserted != expected_chunks:
            print(f"FAIL: expected {expected_chunks} chunks, got {result.chunks_upserted}")
            return 1

        queries = [
            ("FPX transfer credits from Maybank", "transaction"),
            ("statement period and totals", "summary"),
            ("payment to LHDN tax", "transaction"),
        ]
        for q, want_kind in queries:
            hits = store.semantic_search(q, limit=3, document_id="smoke-doc")
            if not hits:
                print(f"FAIL: zero hits for query={q!r}")
                return 1
            top = hits[0]
            print(
                f"  query={q!r:55} -> kind={top.kind:11} score={top.score:.3f} page={top.page}"
            )

        print("PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
