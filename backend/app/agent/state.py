"""Shared state for the credit-assessment LangGraph.

Every node reads from and writes to a single `AgentState`. A few design
choices worth highlighting:

- Each domain output (extraction, validation, ratios, 5C, summary) lives
  in its own typed slot. The graph topology is linear, so nodes only
  *append* — they do not mutate earlier outputs. This makes the state
  history monotonic and audit-friendly (FEATERS Accountability).

- The `trace` list records one `ReasoningStep` per node execution. It is
  the substrate for the explainability layer's source-traced summary.

- `errors` collects non-fatal issues from any node (e.g. one of many
  documents failed to parse). Fatal errors raise — they don't appear
  here.
"""

from __future__ import annotations

import operator
from datetime import datetime
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field

from app.ingestion.types import BankStatement


class ReasoningStep(BaseModel):
    """One node's contribution to the reasoning chain.

    Persisted alongside graph checkpoints so an auditor can replay
    exactly what the agent decided at each step and why.
    """

    node: str
    started_at: datetime
    finished_at: datetime
    summary: str = Field(description="Short human-readable description")
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    citations: list[str] = Field(
        default_factory=list,
        description="Chunk ids consulted in this step",
    )


class AgentError(BaseModel):
    node: str
    message: str
    recoverable: bool = True


class AgentState(TypedDict, total=False):
    """LangGraph state object.

    `total=False` lets nodes return partial dicts; LangGraph merges them
    into the running state. Lists with the `operator.add` annotation
    accumulate across nodes instead of being overwritten.
    """

    # Inputs
    application_id: str
    pdf_paths: list[str]

    # Step 1 — parsing/ingestion
    document_ids: list[str]
    needs_ocr_pages: dict[str, list[int]]  # document_id -> page numbers
    parsed_pages: dict[str, Any]  # document_id -> list[ParsedPage] (internal handoff)

    # Step 2 — structured extraction
    statements: list[BankStatement]

    # Step 3 — cross-document validation (Phase 3b)
    inconsistencies: list[dict[str, Any]]

    # Step 4 — ratios (Phase 3c)
    ratios: dict[str, Any]

    # Step 5 — 5C assessment (Phase 3d)
    five_c: dict[str, Any]

    # Step 6 — explainable summary (Phase 3e)
    risk_summary: str | None

    # Audit + control
    trace: Annotated[list[ReasoningStep], operator.add]
    errors: Annotated[list[AgentError], operator.add]
