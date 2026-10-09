"""Graph tests that run fully offline.

Uses a fake `VectorStore` so we don't hit Qdrant, and the stub embeddings
fallback so we don't hit Gemini. These tests pin down:
- both nodes execute in order,
- `trace` accumulates one ReasoningStep per node,
- a missing input PDF is recorded as a recoverable error, not a crash.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pytest
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import extract_node, parse_node
from app.agent.state import AgentState
from app.ingestion.chunker import Chunk
from app.ingestion.store import VectorStore
from app.ingestion.synthetic import GeneratorConfig, generate


class FakeVectorStore(VectorStore):
    """Records upserts in memory, never touches Qdrant."""

    def __init__(self) -> None:  # noqa: D401
        self.upserted: list[Chunk] = []

    def upsert_chunks(self, chunks: list[Chunk]) -> int:  # type: ignore[override]
        self.upserted.extend(chunks)
        return len(chunks)


def _compile(store: VectorStore):
    graph: StateGraph = StateGraph(AgentState)
    graph.add_node("parse", parse_node)
    graph.add_node("extract", functools.partial(extract_node, store=store))
    graph.add_edge(START, "parse")
    graph.add_edge("parse", "extract")
    graph.add_edge("extract", END)
    return graph.compile()


def test_graph_runs_parse_then_extract(tmp_path: Path) -> None:
    pdf, _ = generate(GeneratorConfig(seed=1, n_transactions=4, num_months=1), tmp_path)
    store = FakeVectorStore()
    graph = _compile(store)

    result = graph.invoke(
        {
            "application_id": "test-app",
            "pdf_paths": [str(pdf)],
            "trace": [],
            "errors": [],
        }
    )

    assert len(result["statements"]) == 1
    assert result["statements"][0].transactions
    assert [s.node for s in result["trace"]] == ["parse", "extract"]
    assert result["errors"] == []
    # 1 summary + 4 transactions
    assert len(store.upserted) == 5


def test_graph_reports_missing_pdf_as_recoverable_error(tmp_path: Path) -> None:
    store = FakeVectorStore()
    graph = _compile(store)

    result = graph.invoke(
        {
            "application_id": "test-app",
            "pdf_paths": [str(tmp_path / "does_not_exist.pdf")],
            "trace": [],
            "errors": [],
        }
    )

    assert result["statements"] == []
    assert result["errors"], "Expected a recoverable error for the missing PDF"
    assert result["errors"][0].node == "parse"
    assert "does_not_exist" in result["errors"][0].message


def test_extract_handles_unparseable_document(tmp_path: Path) -> None:
    """A PDF without the bank-statement header should be reported, not crash."""
    import pymupdf

    blank = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(blank)
    doc.close()

    store = FakeVectorStore()
    graph = _compile(store)
    result = graph.invoke(
        {
            "application_id": "test-app",
            "pdf_paths": [str(blank)],
            "trace": [],
            "errors": [],
        }
    )

    assert result["statements"] == []
    assert any(e.node == "extract" for e in result["errors"])


@pytest.mark.parametrize("n_pdfs", [2, 3])
def test_graph_processes_multiple_pdfs(tmp_path: Path, n_pdfs: int) -> None:
    pdfs = []
    for i in range(n_pdfs):
        pdf, _ = generate(
            GeneratorConfig(seed=i + 10, n_transactions=5),
            tmp_path / f"doc_{i}",
        )
        pdfs.append(str(pdf))
    store = FakeVectorStore()
    graph = _compile(store)

    result = graph.invoke(
        {
            "application_id": "test-app",
            "pdf_paths": pdfs,
            "trace": [],
            "errors": [],
        }
    )

    assert len(result["statements"]) == n_pdfs
    assert len(result["document_ids"]) == n_pdfs
