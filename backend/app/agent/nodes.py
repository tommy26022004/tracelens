"""Node implementations for the credit-assessment graph.

Each node:
- accepts the full `AgentState`,
- returns a partial dict that LangGraph merges into state,
- appends exactly one `ReasoningStep` to `trace`.

Nodes are intentionally thin wrappers over the deterministic services
in `app.ingestion`. The LLM is only invoked for steps that genuinely
need reasoning (validation, 5C, summary — added later). Keeping early
steps deterministic gives a measurable extraction-accuracy baseline
and saves tokens.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.agent.state import AgentError, AgentState, ReasoningStep
from app.ingestion.chunker import chunk_bank_statement
from app.ingestion.extractor import extract_bank_statement
from app.ingestion.parser import parse_pdf
from app.ingestion.store import VectorStore


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_node(state: AgentState) -> dict[str, object]:
    """Step 1 — parse every uploaded PDF and embed chunks into Qdrant.

    Produces `document_ids` and `needs_ocr_pages`. Statements are not
    extracted here; that is the next node's responsibility.
    """
    started = _now()
    pdf_paths = [Path(p) for p in state["pdf_paths"]]
    document_ids: list[str] = []
    needs_ocr: dict[str, list[int]] = {}
    parsed_cache: dict[str, list] = {}
    errors: list[AgentError] = []

    for path in pdf_paths:
        # Include the parent dir so two PDFs with the same basename
        # (common when one SME submits monthly statements with templated
        # filenames) still get distinct document ids.
        document_id = f"{path.parent.name}/{path.stem}" if path.parent.name else path.stem
        try:
            pages = parse_pdf(path)
        except FileNotFoundError as exc:
            errors.append(
                AgentError(node="parse", message=str(exc), recoverable=False)
            )
            continue
        parsed_cache[document_id] = pages
        ocr_pages = [p.page for p in pages if p.needs_ocr]
        if ocr_pages:
            needs_ocr[document_id] = ocr_pages
        document_ids.append(document_id)

    step = ReasoningStep(
        node="parse",
        started_at=started,
        finished_at=_now(),
        summary=f"Parsed {len(document_ids)}/{len(pdf_paths)} PDFs",
        inputs={"pdf_count": len(pdf_paths)},
        outputs={"document_ids": document_ids, "needs_ocr_pages": needs_ocr},
    )
    return {
        "document_ids": document_ids,
        "needs_ocr_pages": needs_ocr,
        "parsed_pages": parsed_cache,  # handoff to extract_node
        "trace": [step],
        "errors": errors,
    }


def extract_node(state: AgentState, *, store: VectorStore | None = None) -> dict[str, object]:
    """Step 2 — turn parsed pages into structured `BankStatement`s and
    upsert citation-preserving chunks into Qdrant.

    The chunk upsert lives here (not in `parse_node`) because the chunker
    needs the structured statement, not raw pages.
    """
    started = _now()
    parsed_cache: dict[str, list] = state.get("parsed_pages", {})  # type: ignore[assignment]
    vector_store = store or VectorStore()

    statements = []
    citations: list[str] = []
    errors: list[AgentError] = []
    chunks_upserted = 0

    for document_id, pages in parsed_cache.items():
        try:
            stmt = extract_bank_statement(pages)
        except ValueError as exc:
            errors.append(
                AgentError(
                    node="extract",
                    message=f"{document_id}: {exc}",
                    recoverable=True,
                )
            )
            continue
        statements.append(stmt)
        chunks = chunk_bank_statement(stmt, document_id=document_id)
        chunks_upserted += vector_store.upsert_chunks(chunks)
        citations.extend(c.chunk_id for c in chunks)

    step = ReasoningStep(
        node="extract",
        started_at=started,
        finished_at=_now(),
        summary=(
            f"Extracted {len(statements)} statements, "
            f"upserted {chunks_upserted} chunks"
        ),
        inputs={"document_ids": list(parsed_cache.keys())},
        outputs={
            "statement_count": len(statements),
            "chunks_upserted": chunks_upserted,
        },
        citations=citations,
    )
    return {
        "statements": statements,
        "trace": [step],
        "errors": errors,
    }
