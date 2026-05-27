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
from app.ingestion.chunker import (
    chunk_audited_financials,
    chunk_bank_statement,
    chunk_ssm_registration,
    chunk_tax_return,
)
from app.ingestion.extractor import extract_bank_statement
from app.ingestion.financials_extractor import extract_audited_financials
from app.ingestion.parser import parse_pdf
from app.ingestion.router import detect_document_kind
from app.ingestion.ssm_extractor import extract_ssm_registration
from app.ingestion.store import VectorStore
from app.ingestion.tax_extractor import extract_tax_return
from app.ingestion.types import DocumentKind
from app.ratios.bank_statement_metrics import compute_metrics
from app.ratios.financial_ratios import compute_financial_ratios
from app.ratios.five_c import FiveCAssessment, build_prompt as build_five_c_prompt
from app.validation.checks import run_checks
from app.validation.cross_doc import run_cross_doc_checks


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_node(state: AgentState) -> dict[str, object]:
    """Step 1 — parse every uploaded PDF and classify its document kind.

    Produces `document_ids`, `document_kinds`, and `needs_ocr_pages`.
    Structured extraction (bank statement / SSM / ...) is the next node's
    responsibility.
    """
    started = _now()
    pdf_paths = [Path(p) for p in state["pdf_paths"]]
    document_ids: list[str] = []
    document_kinds: dict[str, DocumentKind] = {}
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
        document_kinds[document_id] = detect_document_kind(pages)
        document_ids.append(document_id)

    step = ReasoningStep(
        node="parse",
        started_at=started,
        finished_at=_now(),
        summary=(
            f"Parsed {len(document_ids)}/{len(pdf_paths)} PDFs; "
            f"kinds: {sorted({k.value for k in document_kinds.values()})}"
        ),
        inputs={"pdf_count": len(pdf_paths)},
        outputs={
            "document_ids": document_ids,
            "document_kinds": {k: v.value for k, v in document_kinds.items()},
            "needs_ocr_pages": needs_ocr,
        },
    )
    return {
        "document_ids": document_ids,
        "document_kinds": document_kinds,
        "needs_ocr_pages": needs_ocr,
        "parsed_pages": parsed_cache,  # handoff to extract_node
        "trace": [step],
        "errors": errors,
    }


def extract_node(state: AgentState, *, store: VectorStore | None = None) -> dict[str, object]:
    """Step 2 — turn parsed pages into structured documents and upsert
    citation-preserving chunks into Qdrant.

    Routes each document to the right extractor based on the kind that
    `parse_node` detected. Bank statements and SSM forms are supported;
    unknown kinds become a recoverable error so the loan officer knows
    the document was received but couldn't be analysed.
    """
    started = _now()
    parsed_cache: dict[str, list] = state.get("parsed_pages", {})  # type: ignore[assignment]
    document_kinds: dict[str, DocumentKind] = state.get("document_kinds", {})  # type: ignore[assignment]
    vector_store = store or VectorStore()

    statements = []
    ssm_registrations = []
    audited_financials = []
    tax_returns = []
    citations: list[str] = []
    errors: list[AgentError] = []
    chunks_upserted = 0

    for document_id, pages in parsed_cache.items():
        kind = document_kinds.get(document_id, DocumentKind.UNKNOWN)
        try:
            if kind == DocumentKind.BANK_STATEMENT:
                stmt = extract_bank_statement(pages)
                statements.append(stmt)
                chunks = chunk_bank_statement(stmt, document_id=document_id)
            elif kind == DocumentKind.SSM_REGISTRATION:
                ssm = extract_ssm_registration(pages)
                ssm_registrations.append(ssm)
                chunks = chunk_ssm_registration(ssm, document_id=document_id)
            elif kind == DocumentKind.AUDITED_FINANCIALS:
                fin = extract_audited_financials(pages)
                audited_financials.append(fin)
                chunks = chunk_audited_financials(fin, document_id=document_id)
            elif kind == DocumentKind.TAX_RETURN:
                tax = extract_tax_return(pages)
                tax_returns.append(tax)
                chunks = chunk_tax_return(tax, document_id=document_id)
            else:
                errors.append(
                    AgentError(
                        node="extract",
                        message=(
                            f"{document_id}: unsupported document kind ({kind.value}). "
                            f"Add an extractor or remove from the application package."
                        ),
                        recoverable=True,
                    )
                )
                continue
        except ValueError as exc:
            errors.append(
                AgentError(
                    node="extract",
                    message=f"{document_id}: {exc}",
                    recoverable=True,
                )
            )
            continue
        chunks_upserted += vector_store.upsert_chunks(chunks)
        citations.extend(c.chunk_id for c in chunks)

    step = ReasoningStep(
        node="extract",
        started_at=started,
        finished_at=_now(),
        summary=(
            f"Extracted {len(statements)} bank statement(s), "
            f"{len(ssm_registrations)} SSM, "
            f"{len(audited_financials)} audited financials, "
            f"{len(tax_returns)} tax return(s); "
            f"upserted {chunks_upserted} chunks"
        ),
        inputs={"document_ids": list(parsed_cache.keys())},
        outputs={
            "statement_count": len(statements),
            "ssm_count": len(ssm_registrations),
            "financials_count": len(audited_financials),
            "tax_return_count": len(tax_returns),
            "chunks_upserted": chunks_upserted,
        },
        citations=citations,
    )
    return {
        "statements": statements,
        "ssm_registrations": ssm_registrations,
        "audited_financials": audited_financials,
        "tax_returns": tax_returns,
        "trace": [step],
        "errors": errors,
    }


def validate_node(state: AgentState) -> dict[str, object]:
    """Step 3 — deterministic intra-doc + cross-doc validation."""
    started = _now()
    statements = state.get("statements", [])
    ssm_list = state.get("ssm_registrations", [])
    fin_list = state.get("audited_financials", [])
    tax_list = state.get("tax_returns", [])
    bank_doc_ids = _doc_ids_for_kind(state, DocumentKind.BANK_STATEMENT)
    ssm_doc_ids = _doc_ids_for_kind(state, DocumentKind.SSM_REGISTRATION)
    fin_doc_ids = _doc_ids_for_kind(state, DocumentKind.AUDITED_FINANCIALS)
    tax_doc_ids = _doc_ids_for_kind(state, DocumentKind.TAX_RETURN)

    intra = run_checks(statements, bank_doc_ids)
    cross = run_cross_doc_checks(
        statements,
        bank_doc_ids,
        ssm_list,
        ssm_doc_ids,
        fin_list=fin_list,
        fin_doc_ids=fin_doc_ids,
        tax_list=tax_list,
        tax_doc_ids=tax_doc_ids,
    )
    inconsistencies = intra + cross

    payload = [i.model_dump(mode="json") for i in inconsistencies]
    citations = sorted({c for i in inconsistencies for c in i.citations})

    step = ReasoningStep(
        node="validate",
        started_at=started,
        finished_at=_now(),
        summary=(
            f"Validation: {len(intra)} intra-doc + {len(cross)} cross-doc finding(s)"
        ),
        inputs={
            "bank_statement_count": len(statements),
            "ssm_count": len(ssm_list),
        },
        outputs={
            "inconsistency_count": len(inconsistencies),
            "by_severity": _by_severity(inconsistencies),
            "cross_doc_count": len(cross),
        },
        citations=citations,
    )
    return {"inconsistencies": payload, "trace": [step]}


def _doc_ids_for_kind(state: AgentState, kind: DocumentKind) -> list[str]:
    """Return document_ids of a specific kind, in their original parse order.

    Order matters because each kind's structured-extraction list (e.g.
    `statements`) is appended in parse order; downstream checks expect
    the i-th id to match the i-th object.
    """
    document_ids = state.get("document_ids", [])
    document_kinds = state.get("document_kinds", {})
    return [doc_id for doc_id in document_ids if document_kinds.get(doc_id) == kind]


def ratios_node(state: AgentState) -> dict[str, object]:
    """Step 4 — compute bank-statement metrics and (when audited financials
    are present) the standard 5C financial ratios.

    The two outputs live under separate keys so the dashboard and 5C
    prompt can distinguish bank-only signals from audited ratios.
    """
    started = _now()
    statements = state.get("statements", [])
    fin_list = state.get("audited_financials", [])
    bank_doc_ids = _doc_ids_for_kind(state, DocumentKind.BANK_STATEMENT)
    fin_doc_ids = _doc_ids_for_kind(state, DocumentKind.AUDITED_FINANCIALS)

    metrics = [
        compute_metrics(stmt, doc_id)
        for stmt, doc_id in zip(statements, bank_doc_ids, strict=True)
    ]
    financial_ratios = [
        compute_financial_ratios(fin, doc_id)
        for fin, doc_id in zip(fin_list, fin_doc_ids, strict=True)
    ]
    payload = {
        "bank_statement_metrics": [m.model_dump(mode="json") for m in metrics],
        "financial_ratios": [r.model_dump(mode="json") for r in financial_ratios],
    }

    step = ReasoningStep(
        node="ratios",
        started_at=started,
        finished_at=_now(),
        summary=(
            f"Computed bank metrics for {len(metrics)} statement(s); "
            f"financial ratios for {len(financial_ratios)} audited set(s)"
        ),
        inputs={
            "statement_count": len(statements),
            "audited_financials_count": len(fin_list),
        },
        outputs={
            "bank_metric_count": len(metrics),
            "financial_ratio_set_count": len(financial_ratios),
        },
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
    ssm_list = state.get("ssm_registrations", [])
    fin_list = state.get("audited_financials", [])
    tax_list = state.get("tax_returns", [])
    bank_doc_ids = _doc_ids_for_kind(state, DocumentKind.BANK_STATEMENT)
    ssm_doc_ids = _doc_ids_for_kind(state, DocumentKind.SSM_REGISTRATION)
    fin_doc_ids = _doc_ids_for_kind(state, DocumentKind.AUDITED_FINANCIALS)
    tax_doc_ids = _doc_ids_for_kind(state, DocumentKind.TAX_RETURN)

    metrics = [
        compute_metrics(stmt, doc_id)
        for stmt, doc_id in zip(statements, bank_doc_ids, strict=True)
    ]
    financial_ratios = [
        compute_financial_ratios(fin, doc_id)
        for fin, doc_id in zip(fin_list, fin_doc_ids, strict=True)
    ]
    inconsistencies = run_checks(statements, bank_doc_ids) + run_cross_doc_checks(
        statements,
        bank_doc_ids,
        ssm_list,
        ssm_doc_ids,
        fin_list=fin_list,
        fin_doc_ids=fin_doc_ids,
        tax_list=tax_list,
        tax_doc_ids=tax_doc_ids,
    )

    prompt = build_five_c_prompt(metrics, inconsistencies, financial_ratios=financial_ratios)
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
    ssm_list = state.get("ssm_registrations", [])
    fin_list = state.get("audited_financials", [])
    tax_list = state.get("tax_returns", [])
    bank_doc_ids = _doc_ids_for_kind(state, DocumentKind.BANK_STATEMENT)
    ssm_doc_ids = _doc_ids_for_kind(state, DocumentKind.SSM_REGISTRATION)
    fin_doc_ids = _doc_ids_for_kind(state, DocumentKind.AUDITED_FINANCIALS)
    tax_doc_ids = _doc_ids_for_kind(state, DocumentKind.TAX_RETURN)
    five_c_payload = state.get("five_c", {})
    if not five_c_payload:
        raise ValueError("summarise_node requires five_c output from assess_5c_node")
    five_c = FiveCAssessment.model_validate(five_c_payload)

    metrics = [
        compute_metrics(stmt, doc_id)
        for stmt, doc_id in zip(statements, bank_doc_ids, strict=True)
    ]
    financial_ratios = [
        compute_financial_ratios(fin, doc_id)
        for fin, doc_id in zip(fin_list, fin_doc_ids, strict=True)
    ]
    inconsistencies = run_checks(statements, bank_doc_ids) + run_cross_doc_checks(
        statements,
        bank_doc_ids,
        ssm_list,
        ssm_doc_ids,
        fin_list=fin_list,
        fin_doc_ids=fin_doc_ids,
        tax_list=tax_list,
        tax_doc_ids=tax_doc_ids,
    )

    allowed_chunk_ids: list[str] = []
    for stmt, doc_id in zip(statements, bank_doc_ids, strict=True):
        allowed_chunk_ids.append(f"{doc_id}:summary:0")
        for idx in range(len(stmt.transactions)):
            allowed_chunk_ids.append(f"{doc_id}:transaction:{idx}")
    for ssm, doc_id in zip(ssm_list, ssm_doc_ids, strict=True):
        allowed_chunk_ids.append(f"{doc_id}:summary:0")
        for idx in range(len(ssm.directors)):
            allowed_chunk_ids.append(f"{doc_id}:director:{idx}")
    for fin, doc_id in zip(fin_list, fin_doc_ids, strict=True):
        allowed_chunk_ids.append(f"{doc_id}:summary:0")
        for idx in range(len(fin.periods)):
            allowed_chunk_ids.append(f"{doc_id}:period:{idx}")
    for _tax, doc_id in zip(tax_list, tax_doc_ids, strict=True):
        allowed_chunk_ids.append(f"{doc_id}:summary:0")

    prompt = build_summary_prompt(
        metrics, inconsistencies, five_c, allowed_chunk_ids, financial_ratios=financial_ratios
    )
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
