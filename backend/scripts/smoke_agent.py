"""End-to-end smoke test for the Phase 3a graph (parse + extract nodes).

Generates a synthetic statement, runs it through the compiled graph,
prints the resulting state + trace. Exits non-zero on failure.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from app.agent.graph import compile_graph
from app.ingestion.store import COLLECTION_NAME, VectorStore
from app.ingestion.synthetic import GeneratorConfig, generate


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        pdf, _ = generate(GeneratorConfig(seed=314, n_transactions=12), Path(tmp))

        store = VectorStore()
        if store._client.collection_exists(COLLECTION_NAME):  # noqa: SLF001
            store._client.delete_collection(COLLECTION_NAME)  # noqa: SLF001

        graph = compile_graph()
        config = {"configurable": {"thread_id": "smoke-agent-1"}}
        result = graph.invoke(
            {
                "application_id": "smoke-app",
                "pdf_paths": [str(pdf)],
                "trace": [],
                "errors": [],
            },
            config=config,
        )

        print(f"document_ids: {result.get('document_ids')}")
        print(f"statements  : {len(result.get('statements', []))}")
        print(f"errors      : {result.get('errors')}")
        print()
        print("Reasoning trail:")
        for step in result.get("trace", []):
            duration_ms = (step.finished_at - step.started_at).total_seconds() * 1000
            print(f"  [{step.node:8}] {duration_ms:6.1f}ms  {step.summary}")

        if not result.get("statements"):
            print("FAIL: no statements extracted")
            return 1
        if result.get("errors"):
            print(f"FAIL: errors present: {result['errors']}")
            return 1
        print("PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
