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
from app.core.llm import LLMProvider, get_llm
from app.explainability.summary import (
    RiskSummary,
    build_prompt as build_summary_prompt,
    extract_citations,
)
from app.ingestion.chunker import chunk_bank_statement
from app.ingestion.extractor import extract_bank_statement
from app.ingestion.parser import parse_pdf
from app.ingestion.store import VectorStore
from app.ratios.bank_statement_metrics import compute_metrics
from app.ratios.five_c import FiveCAssessment, build_prompt as build_five_c_prompt
from app.validation.checks import run_checks


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


def validate_node(state: AgentState) -> dict[str, object]:
    """Step 3 — deterministic cross-doc / intra-doc validation."""
    started = _now()
    statements = state.get("statements", [])
    document_ids = state.get("document_ids", [])
    # Align by index — `extract_node` writes them in matching order, but
    # only documents that successfully extracted appear in `statements`.
    aligned_doc_ids = document_ids[: len(statements)]

    inconsistencies = run_checks(statements, aligned_doc_ids)
    payload = [i.model_dump(mode="json") for i in inconsistencies]
    citations = sorted({c for i in inconsistencies for c in i.citations})

    step = ReasoningStep(
        node="validate",
        started_at=started,
        finished_at=_now(),
        summary=f"Ran deterministic checks; {len(inconsistencies)} finding(s)",
        inputs={"statement_count": len(statements)},
        outputs={
            "inconsistency_count": len(inconsistencies),
            "by_severity": _by_severity(inconsistencies),
        },
        citations=citations,
    )
    return {"inconsistencies": payload, "trace": [step]}


def ratios_node(state: AgentState) -> dict[str, object]:
    """Step 4 — compute bank-statement-derivable metrics."""
    started = _now()
    statements = state.get("statements", [])
    document_ids = state.get("document_ids", [])[: len(statements)]

    metrics = [
        compute_metrics(stmt, doc_id)
        for stmt, doc_id in zip(statements, document_ids, strict=True)
    ]
    payload = {
        "bank_statement_metrics": [m.model_dump(mode="json") for m in metrics]
    }

    step = ReasoningStep(
        node="ratios",
        started_at=started,
        finished_at=_now(),
        summary=f"Computed metrics for {len(metrics)} statement(s)",
        inputs={"statement_count": len(statements)},
        outputs={"metric_set_count": len(metrics)},
    )
    return {"ratios": payload, "trace": [step]}


def assess_5c_node(
    state: AgentState,
    *,
    llm: LLMProvider | None = None,
) -> dict[str, object]:
    """Step 5 — 5C credit assessment via structured LLM output."""
    started = _now()
    statements = state.get("statements", [])
    document_ids = state.get("document_ids", [])[: len(statements)]

    metrics = [
        compute_metrics(stmt, doc_id)
        for stmt, doc_id in zip(statements, document_ids, strict=True)
    ]
    inconsistencies = run_checks(statements, document_ids)

    prompt = build_five_c_prompt(metrics, inconsistencies)
    provider = llm or get_llm()
    assessment = provider.generate_structured(prompt, FiveCAssessment)

    citations: list[str] = []
    for dim in (
        assessment.character,
        assessment.capacity,
        assessment.capital,
        assessment.collateral,
        assessment.conditions,
    ):
        citations.extend(dim.evidence_chunk_ids)

    step = ReasoningStep(
        node="assess_5c",
        started_at=started,
        finished_at=_now(),
        summary=(
            "5C assessment: "
            + ", ".join(
                f"{dim.name}={dim.rating.value}"
                for dim in (
                    assessment.character,
                    assessment.capacity,
                    assessment.capital,
                    assessment.collateral,
                    assessment.conditions,
                )
            )
        ),
        inputs={"metric_sets": len(metrics), "inconsistencies": len(inconsistencies)},
        outputs=assessment.model_dump(mode="json"),
        citations=sorted(set(citations)),
    )
    return {
        "five_c": assessment.model_dump(mode="json"),
        "trace": [step],
    }


def summarise_node(
    state: AgentState,
    *,
    llm: LLMProvider | None = None,
) -> dict[str, object]:
    """Step 6 — produce a source-traced natural-language risk summary."""
    started = _now()
    statements = state.get("statements", [])
    document_ids = state.get("document_ids", [])[: len(statements)]
    five_c_payload = state.get("five_c", {})
    if not five_c_payload:
        raise ValueError("summarise_node requires five_c output from assess_5c_node")
    five_c = FiveCAssessment.model_validate(five_c_payload)

    metrics = [
        compute_metrics(stmt, doc_id)
        for stmt, doc_id in zip(statements, document_ids, strict=True)
    ]
    inconsistencies = run_checks(statements, document_ids)

    allowed_chunk_ids: list[str] = []
    for stmt, doc_id in zip(statements, document_ids, strict=True):
        allowed_chunk_ids.append(f"{doc_id}:summary:0")
        for idx in range(len(stmt.transactions)):
            allowed_chunk_ids.append(f"{doc_id}:transaction:{idx}")

    prompt = build_summary_prompt(metrics, inconsistencies, five_c, allowed_chunk_ids)
    provider = llm or get_llm()
    summary = provider.generate_structured(prompt, RiskSummary)

    # Verify every cited chunk_id is real. We don't re-prompt the LLM —
    # we surface the discrepancy as a recoverable error so the dashboard
    # can show the loan officer that the AI cited something unverifiable.
    cited = set(
        extract_citations(summary.headline) + extract_citations(summary.body)
    )
    summary.cited_chunk_ids = sorted(cited)
    invalid = sorted(cited - set(allowed_chunk_ids))
    errors: list[AgentError] = []
    if invalid:
        errors.append(
            AgentError(
                node="summarise",
                message=(
                    f"Summary references chunk_ids not produced by ingestion: {invalid}. "
                    f"Loan officer should treat affected claims as unverified."
                ),
                recoverable=True,
            )
        )

    step = ReasoningStep(
        node="summarise",
        started_at=started,
        finished_at=_now(),
        summary=f"Generated risk summary with {len(cited)} citation(s)",
        inputs={"allowed_citations": len(allowed_chunk_ids)},
        outputs={"cited": sorted(cited), "invalid_citations": invalid},
        citations=sorted(cited & set(allowed_chunk_ids)),
    )
    return {
        "risk_summary": summary.model_dump_json(),
        "trace": [step],
        "errors": errors,
    }


def _by_severity(inconsistencies: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in inconsistencies:
        sev = issue.severity.value
        counts[sev] = counts.get(sev, 0) + 1
    return counts
