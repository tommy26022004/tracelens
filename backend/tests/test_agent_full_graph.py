"""Offline integration test for the full 6-node graph.

Uses a fake `VectorStore` and a fake `LLMProvider` so the test never
touches Qdrant or Gemini. The fake LLM returns a fixed `FiveCAssessment`
and a `RiskSummary` whose citations come from the live ingestion run.
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import TypeVar

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.agent.nodes import (
    assess_5c_node,
    extract_node,
    parse_node,
    ratios_node,
    summarise_node,
    validate_node,
)
from app.agent.state import AgentState
from app.explainability.summary import RiskSummary
from app.ingestion.chunker import Chunk
from app.ingestion.store import RetrievalHit, VectorStore
from app.ingestion.synthetic import GeneratorConfig, generate
from app.ratios.five_c import Dimension, FiveCAssessment, Rating

T = TypeVar("T", bound=BaseModel)


class FakeVectorStore(VectorStore):
    def __init__(self) -> None:  # noqa: D401
        self.upserted: list[Chunk] = []

    def upsert_chunks(self, chunks: list[Chunk]) -> int:  # type: ignore[override]
        self.upserted.extend(chunks)
        return len(chunks)

    @property
    def embedding_space(self) -> str:
        return "test-lexical-v1"

    def semantic_search(
        self,
        query,
        *,
        application_id=None,
        document_kinds=None,
        limit=5,
        score_threshold=None,
        **kwargs,
    ):
        words = set(re.findall(r"[a-z]+", query.lower()))
        hits = []
        for chunk in self.upserted:
            if chunk.source_metadata.get("application_id") != application_id:
                continue
            if document_kinds and chunk.source_metadata.get("document_kind") not in document_kinds:
                continue
            score = len(words & set(re.findall(r"[a-z]+", chunk.text.lower()))) / max(len(words), 1)
            if score < (score_threshold or 0):
                continue
            hits.append(
                RetrievalHit(
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.kind,
                    chunk.text,
                    chunk.page,
                    score,
                    chunk.source_metadata,
                )
            )
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]


class FakeLLM:
    """Deterministic stand-in for `LLMProvider`."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, type]] = []

    def generate_text(self, prompt: str) -> str:  # pragma: no cover
        self.calls.append((prompt, str))
        return ""

    def generate_structured(self, prompt: str, schema: type[T]) -> T:  # type: ignore[override]
        self.calls.append((prompt, schema))
        if schema is FiveCAssessment:
            return schema(  # type: ignore[return-value]
                character=Dimension(
                    name="Character",
                    rating=Rating.ADEQUATE,
                    reasoning="Stable counterparties.",
                    evidence_chunk_ids=["fake-doc:summary:0"],
                ),
                capacity=Dimension(
                    name="Capacity",
                    rating=Rating.ADEQUATE,
                    reasoning="Positive net change.",
                    evidence_chunk_ids=["fake-doc:summary:0"],
                ),
                capital=Dimension(
                    name="Capital",
                    rating=Rating.INSUFFICIENT_DATA,
                    reasoning="No audited financials supplied.",
                    evidence_chunk_ids=[],
                    flags_for_human_review=["Request audited financials"],
                ),
                collateral=Dimension(
                    name="Collateral",
                    rating=Rating.INSUFFICIENT_DATA,
                    reasoning="No asset schedule.",
                    evidence_chunk_ids=[],
                    flags_for_human_review=["Request CTOS / asset schedule"],
                ),
                conditions=Dimension(
                    name="Conditions",
                    rating=Rating.ADEQUATE,
                    reasoning="Diverse counterparties.",
                    evidence_chunk_ids=["fake-doc:summary:0"],
                ),
            )
        if schema is RiskSummary:
            # Pull a real chunk_id out of the prompt so citation validation
            # passes — the prompt lists allowed chunk_ids in plain text.
            sample = self._first_chunk_id(prompt)
            return schema(  # type: ignore[return-value]
                headline=f"Cash-flow positive applicant with limited multi-doc evidence [{sample}].",
                body=(
                    f"Bank statement shows positive net change over the period [{sample}]. "
                    f"Capital and collateral cannot be assessed from bank data alone [{sample}]."
                ),
                recommended_human_checks=[
                    "Request audited financials",
                    "Request CTOS / asset schedule",
                ],
                cited_chunk_ids=[],
            )
        raise NotImplementedError(schema)

    @staticmethod
    def _first_chunk_id(prompt: str) -> str:
        # The summary prompt lists allowed chunk_ids on the line directly
        # after the "Allowed chunk_ids" header.
        lines = prompt.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("Allowed chunk_ids"):
                listing = lines[i + 1] if i + 1 < len(lines) else ""
                return listing.split(",")[0].strip()
        return "fake-doc:summary:0"


class UnavailableLLM:
    def generate_text(self, prompt: str) -> str:
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    def generate_structured(self, prompt: str, schema: type[T]) -> T:
        raise RuntimeError("429 RESOURCE_EXHAUSTED")


def _compile(store: VectorStore, llm) -> object:
    graph: StateGraph = StateGraph(AgentState)
    graph.add_node("parse", parse_node)
    graph.add_node("extract", functools.partial(extract_node, store=store))
    graph.add_node("validate", validate_node)
    graph.add_node("ratios", ratios_node)
    graph.add_node("assess_5c", functools.partial(assess_5c_node, llm=llm, store=store))
    graph.add_node("summarise", functools.partial(summarise_node, llm=llm))
    graph.add_edge(START, "parse")
    graph.add_edge("parse", "extract")
    graph.add_edge("extract", "validate")
    graph.add_edge("validate", "ratios")
    graph.add_edge("ratios", "assess_5c")
    graph.add_edge("assess_5c", "summarise")
    graph.add_edge("summarise", END)
    return graph.compile()


def test_full_graph_offline(tmp_path: Path) -> None:
    pdf, _ = generate(GeneratorConfig(seed=42, n_transactions=6), tmp_path)
    store = FakeVectorStore()
    llm = FakeLLM()
    graph = _compile(store, llm)

    result = graph.invoke(
        {
            "application_id": "test-app",
            "pdf_paths": [str(pdf)],
            "trace": [],
            "errors": [],
        }
    )

    assert [s.node for s in result["trace"]] == [
        "parse",
        "extract",
        "validate",
        "ratios",
        "assess_5c",
        "summarise",
    ]

    # validate: clean synthetic statement should produce no critical issues
    assert all(i["severity"] != "critical" for i in result.get("inconsistencies", []))

    # ratios populated
    assert "bank_statement_metrics" in result["ratios"]

    # 5C present with 5 dimensions
    five_c = result["five_c"]
    assert set(five_c.keys()) == {
        "character",
        "capacity",
        "capital",
        "collateral",
        "conditions",
    }

    # Summary is JSON, has citations, all citations are allowed chunk_ids
    summary = json.loads(result["risk_summary"])
    assert summary["headline"]
    assert summary["cited_chunk_ids"], "Summary must cite at least one chunk_id"
    # No invalid-citation errors should have been raised
    assert all(e.node != "summarise" for e in result["errors"])


def test_full_graph_completes_with_deterministic_fallback(tmp_path: Path) -> None:
    pdf, _ = generate(GeneratorConfig(seed=42, n_transactions=6), tmp_path)
    graph = _compile(FakeVectorStore(), UnavailableLLM())

    result = graph.invoke(
        {
            "application_id": "fallback-app",
            "pdf_paths": [str(pdf)],
            "trace": [],
            "errors": [],
        }
    )

    assert [step.node for step in result["trace"]] == [
        "parse",
        "extract",
        "validate",
        "ratios",
        "assess_5c",
        "summarise",
    ]
    assert result["five_c"]["collateral"]["rating"] == "insufficient_data"
    assert json.loads(result["risk_summary"])["headline"]
    assert {error.node for error in result["errors"]} == {"assess_5c", "summarise"}
