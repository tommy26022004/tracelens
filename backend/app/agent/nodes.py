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

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.agent.fallback_reasoning import build_fallback_five_c, build_fallback_summary
from app.agent.retrieval import (
    RetrievalBundle,
    context_citations,
    evidence_prompt,
    retrieve_evidence,
    tax_evidence,
)
from app.agent.state import AgentError, AgentState, ReasoningStep
from app.core.llm import LLMProvider, get_llm
from app.explainability.summary import (
    RiskSummary,
    extract_citations,
    has_unsupported_critical_label,
    normalise_inventory_headline_citations,
)
from app.explainability.summary import (
    build_prompt as build_summary_prompt,
)
from app.ingestion.chunker import (
    chunk_audited_financials,
    chunk_bank_statement,
    chunk_ssm_registration,
    chunk_tax_return,
    chunk_unstructured_pages,
)
from app.ingestion.extractor import extract_bank_statement
from app.ingestion.financials_extractor import extract_audited_financials
from app.ingestion.package_inventory import build_package_inventory
from app.ingestion.parser import parse_pdf
from app.ingestion.router import detect_document_kind
from app.ingestion.ssm_extractor import extract_ssm_registration
from app.ingestion.store import VectorStore
from app.ingestion.tax_extractor import extract_tax_return
from app.ingestion.types import DocumentKind
from app.ratios.bank_statement_metrics import BankStatementMetrics, compute_metrics
from app.ratios.financial_ratios import FinancialRatios, compute_financial_ratios
from app.ratios.five_c import FiveCAssessment
from app.ratios.five_c import build_prompt as build_five_c_prompt
from app.ratios.package_metrics import compute_financial_trend, compute_package_cash_flow
from app.validation.checks import Inconsistency, run_checks
from app.validation.cross_doc import run_cross_doc_checks
from app.validation.package_checks import run_package_checks


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _allowed_chunk_ids(
    statements,
    bank_doc_ids: list[str],
    ssm_list,
    ssm_doc_ids: list[str],
    fin_list,
    fin_doc_ids: list[str],
    tax_list,
    tax_doc_ids: list[str],
) -> list[str]:
    allowed: list[str] = []
    for stmt, doc_id in zip(statements, bank_doc_ids, strict=True):
        allowed.append(f"{doc_id}:summary:0")
        allowed.extend(f"{doc_id}:transaction:{idx}" for idx in range(len(stmt.transactions)))
    for ssm, doc_id in zip(ssm_list, ssm_doc_ids, strict=True):
        allowed.append(f"{doc_id}:summary:0")
        allowed.extend(f"{doc_id}:director:{idx}" for idx in range(len(ssm.directors)))
    for fin, doc_id in zip(fin_list, fin_doc_ids, strict=True):
        allowed.append(f"{doc_id}:summary:0")
        allowed.extend(f"{doc_id}:period:{idx}" for idx in range(len(fin.periods)))
    allowed.extend(
        f"{doc_id}:summary:0" for _tax, doc_id in zip(tax_list, tax_doc_ids, strict=True)
    )
    return allowed


def _five_c_invalid_citations(assessment: FiveCAssessment, allowed: set[str]) -> list[str]:
    cited = {
        citation
        for dimension in (
            assessment.character,
            assessment.capacity,
            assessment.capital,
            assessment.collateral,
            assessment.conditions,
        )
        for citation in dimension.evidence_chunk_ids
    }
    return sorted(cited - allowed)


def _filter_five_c_citations(assessment: FiveCAssessment, allowed: set[str]) -> None:
    for dimension in (
        assessment.character,
        assessment.capacity,
        assessment.capital,
        assessment.collateral,
        assessment.conditions,
    ):
        dimension.evidence_chunk_ids = sorted(
            {citation for citation in dimension.evidence_chunk_ids if citation in allowed}
        )


def _filter_inline_citations(text: str, allowed: set[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        valid = [citation for citation in extract_citations(match.group(0)) if citation in allowed]
        return "".join(f"[{citation}]" for citation in valid)

    return re.sub(r"\[[^\[\]]+?\]", replace, text)


def _high_management_concentration(
    retrieval: RetrievalBundle,
    *,
    threshold: float = 50.0,
) -> tuple[list[float], list[str]]:
    percentages: set[float] = set()
    chunk_ids: list[str] = []
    for item in retrieval.evidence:
        if item.document_kind != "management_accounts":
            continue
        item_percentages: set[float] = set()
        for line in item.text.splitlines():
            lowered = line.lower()
            if not any(
                term in lowered
                for term in (
                    "customer concentration",
                    "supplier dependence",
                    "supplier concentration",
                )
            ):
                continue
            item_percentages.update(
                float(value)
                for value in re.findall(r"(?<!\d)(\d{1,3}(?:\.\d+)?)\s*%", line)
                if float(value) >= threshold
            )
        if item_percentages:
            percentages.update(item_percentages)
            chunk_ids.append(item.chunk_id)
    return sorted(percentages), list(dict.fromkeys(chunk_ids))


def _clean_human_checks(checks: list[str], finding_codes: set[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw_check in checks:
        check = raw_check.strip()
        if not check:
            continue
        if any(
            re.match(rf"^{re.escape(code)}\s*:", check, re.IGNORECASE) for code in finding_codes
        ):
            continue
        lowered = check.lower()
        if "repayment" in lowered or "debt service" in lowered:
            category = "repayment"
        elif "bank statement" in lowered or "banking history" in lowered:
            category = "bank_evidence"
        elif "audited financial" in lowered:
            category = "audited_financials"
        elif "ssm" in lowered or "registration status" in lowered:
            category = "registration"
        elif any(
            term in lowered for term in ("collateral", "facility statement", "security document")
        ):
            category = "collateral"
        elif "management account" in lowered or "industry condition" in lowered:
            category = "conditions"
        else:
            category = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
        if category in seen:
            continue
        seen.add(category)
        cleaned.append(check)
    return cleaned


def _all_uploaded_documents_failed(state: AgentState) -> bool:
    inventory = state.get("package_inventory", {})
    return (
        inventory.get("total_documents", 0) > 0
        and inventory.get("extracted_documents", 0) == 0
        and inventory.get("failed_documents", 0) == inventory.get("total_documents", 0)
    )


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
    document_hashes: dict[str, str] = {}
    document_paths: dict[str, str] = {}
    document_filenames: dict[str, str] = {}
    parse_failures: dict[str, str] = {}
    errors: list[AgentError] = []

    for path in pdf_paths:
        # Include the parent dir so two PDFs with the same basename
        # (common when one SME submits monthly statements with templated
        # filenames) still get distinct document ids.
        base_document_id = f"{path.parent.name}/{path.stem}" if path.parent.name else path.stem
        document_id = base_document_id
        collision_index = 2
        while document_id in parsed_cache:
            document_id = f"{base_document_id}__{collision_index}"
            collision_index += 1
        document_paths[document_id] = str(path)
        document_filenames[document_id] = state.get("original_filenames", {}).get(
            str(path), path.name
        )
        try:
            document_hashes[document_id] = hashlib.sha256(path.read_bytes()).hexdigest()
            pages = parse_pdf(path)
        except FileNotFoundError as exc:
            errors.append(AgentError(node="parse", message=str(exc), recoverable=False))
            continue
        except RuntimeError:
            filename = document_filenames[document_id]
            message = (
                f"{filename} could not be opened as a valid PDF. The file may be damaged "
                "or incomplete; replace it and retry."
            )
            parsed_cache[document_id] = []
            document_kinds[document_id] = DocumentKind.UNKNOWN
            document_ids.append(document_id)
            parse_failures[document_id] = message
            errors.append(AgentError(node="parse", message=message, recoverable=True))
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
            f"Parsed {len(document_ids) - len(parse_failures)}/{len(pdf_paths)} PDFs; "
            f"kinds: {sorted({k.value for k in document_kinds.values()})}"
        ),
        inputs={"pdf_count": len(pdf_paths)},
        outputs={
            "document_ids": document_ids,
            "document_kinds": {k: v.value for k, v in document_kinds.items()},
            "needs_ocr_pages": needs_ocr,
            "parse_failure_count": len(parse_failures),
        },
    )
    return {
        "document_ids": document_ids,
        "document_kinds": document_kinds,
        "document_hashes": document_hashes,
        "document_paths": document_paths,
        "document_filenames": document_filenames,
        "needs_ocr_pages": needs_ocr,
        "document_parse_failures": parse_failures,
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
    extracted_document_ids: dict[str, list[str]] = {}
    extracted_metadata: dict[str, dict[str, object]] = {}
    citation_sources: dict[str, dict] = {}

    for document_id, pages in parsed_cache.items():
        kind = document_kinds.get(document_id, DocumentKind.UNKNOWN)
        if document_id in state.get("document_parse_failures", {}):
            extracted_metadata[document_id] = {"status": "parse_failed"}
            continue
        try:
            if kind == DocumentKind.BANK_STATEMENT:
                stmt = extract_bank_statement(pages)
                statements.append(stmt)
                chunks = chunk_bank_statement(stmt, document_id=document_id)
                extracted_metadata[document_id] = {
                    "status": "extracted",
                    "account_number": stmt.account_number,
                    "period_start": stmt.statement_period_start.isoformat(),
                    "period_end": stmt.statement_period_end.isoformat(),
                }
            elif kind == DocumentKind.SSM_REGISTRATION:
                ssm = extract_ssm_registration(pages)
                ssm_registrations.append(ssm)
                chunks = chunk_ssm_registration(ssm, document_id=document_id)
                extracted_metadata[document_id] = {"status": "extracted"}
            elif kind == DocumentKind.AUDITED_FINANCIALS:
                fin = extract_audited_financials(pages)
                audited_financials.append(fin)
                chunks = chunk_audited_financials(fin, document_id=document_id)
                extracted_metadata[document_id] = {
                    "status": "extracted",
                    "financial_year": fin.financial_year_end.year,
                }
            elif kind == DocumentKind.TAX_RETURN:
                tax = extract_tax_return(pages)
                tax_returns.append(tax)
                chunks = chunk_tax_return(tax, document_id=document_id)
                extracted_metadata[document_id] = {
                    "status": "extracted",
                    "financial_year": tax.year_of_assessment,
                }
            elif kind in {
                DocumentKind.MANAGEMENT_ACCOUNTS,
                DocumentKind.CASH_FLOW_FORECAST,
                DocumentKind.FACILITY_STATEMENT,
            }:
                chunks = chunk_unstructured_pages(pages, document_id, kind.value)
                extracted_metadata[document_id] = {"status": "indexed"}
            else:
                ocr_pages = state.get("needs_ocr_pages", {}).get(document_id, [])
                if ocr_pages:
                    extracted_metadata[document_id] = {"status": "ocr_required"}
                    page_label = ", ".join(str(page) for page in ocr_pages)
                    message = (
                        f"{document_id}: image-only or insufficient-text PDF detected on "
                        f"page(s) {page_label}; OCR is required but is not currently supported."
                    )
                else:
                    message = (
                        f"{document_id}: unsupported document kind ({kind.value}). "
                        "Add an extractor or remove it from the application package."
                    )
                errors.append(
                    AgentError(
                        node="extract",
                        message=message,
                        recoverable=True,
                    )
                )
                continue
            extracted_document_ids.setdefault(kind.value, []).append(document_id)
        except ValueError as exc:
            errors.append(
                AgentError(
                    node="extract",
                    message=f"{document_id}: {exc}",
                    recoverable=True,
                )
            )
            continue
        filename = state.get("document_filenames", {}).get(document_id, document_id)
        for chunk in chunks:
            source_pages = chunk.source_metadata.get(
                "source_pages", [chunk.page] if chunk.page else []
            )
            chunk.source_metadata.update(
                filename=filename,
                application_id=state.get("application_id"),
                document_kind=kind.value,
                source_pages=source_pages,
            )
            citation_sources[chunk.chunk_id] = {
                "document_id": document_id,
                "filename": filename,
                "pages": source_pages,
            }
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
    inventory = build_package_inventory(
        state.get("document_ids", []),
        document_kinds,
        parsed_cache,
        state.get("document_hashes", {}),
        extracted_metadata,
    )
    return {
        "statements": statements,
        "ssm_registrations": ssm_registrations,
        "audited_financials": audited_financials,
        "tax_returns": tax_returns,
        "extracted_document_ids": extracted_document_ids,
        "package_inventory": inventory.model_dump(mode="json"),
        "citation_sources": citation_sources,
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
    package_findings = run_package_checks(state.get("package_inventory", {}), fin_list, fin_doc_ids)
    inconsistencies = intra + cross + package_findings

    payload = [i.model_dump(mode="json") for i in inconsistencies]
    citations = sorted({c for i in inconsistencies for c in i.citations})

    step = ReasoningStep(
        node="validate",
        started_at=started,
        finished_at=_now(),
        summary=(
            f"Validation: {len(intra)} intra-doc + {len(cross)} cross-doc + "
            f"{len(package_findings)} package finding(s)"
        ),
        inputs={
            "bank_statement_count": len(statements),
            "ssm_count": len(ssm_list),
        },
        outputs={
            "inconsistency_count": len(inconsistencies),
            "by_severity": _by_severity(inconsistencies),
            "cross_doc_count": len(cross),
            "package_finding_count": len(package_findings),
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
    extracted_ids = state.get("extracted_document_ids", {})
    if kind.value in extracted_ids:
        return extracted_ids[kind.value]
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
        compute_metrics(stmt, doc_id) for stmt, doc_id in zip(statements, bank_doc_ids, strict=True)
    ]
    financial_ratios = [
        compute_financial_ratios(fin, doc_id)
        for fin, doc_id in zip(fin_list, fin_doc_ids, strict=True)
    ]
    package_cash_flow = compute_package_cash_flow(statements)
    financial_trend = compute_financial_trend(fin_list)
    payload = {
        "bank_statement_metrics": [m.model_dump(mode="json") for m in metrics],
        "financial_ratios": [r.model_dump(mode="json") for r in financial_ratios],
        "package_cash_flow": package_cash_flow.model_dump(mode="json"),
        "financial_trend": financial_trend.model_dump(mode="json"),
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


def _assessment_evidence(state: AgentState):
    if "ratios" not in state or "inconsistencies" not in state:
        raise ValueError("Assessment requires the validation and ratios outputs")
    ratios = state["ratios"]
    metrics = [
        BankStatementMetrics.model_validate(item)
        for item in ratios.get("bank_statement_metrics", [])
    ]
    financial_ratios = [
        FinancialRatios.model_validate(item) for item in ratios.get("financial_ratios", [])
    ]
    findings = [Inconsistency.model_validate(item) for item in state["inconsistencies"]]
    return metrics, financial_ratios, findings


def _package_evidence(state: AgentState) -> str:
    bank_ids = _doc_ids_for_kind(state, DocumentKind.BANK_STATEMENT)
    bank_accounts: dict[tuple[str, str, str], dict[str, object]] = {}
    for statement, document_id in zip(state.get("statements", []), bank_ids, strict=True):
        key = (statement.bank_name, statement.account_holder, statement.account_number)
        account = bank_accounts.setdefault(
            key,
            {
                "bank_name": statement.bank_name,
                "account_holder": statement.account_holder,
                "account_number": statement.account_number,
                "statement_count": 0,
                "period_start": statement.statement_period_start.isoformat(),
                "period_end": statement.statement_period_end.isoformat(),
                "first_document_id": document_id,
                "last_document_id": document_id,
            },
        )
        account["statement_count"] = int(account["statement_count"]) + 1
        if statement.statement_period_start.isoformat() < str(account["period_start"]):
            account["period_start"] = statement.statement_period_start.isoformat()
            account["first_document_id"] = document_id
        if statement.statement_period_end.isoformat() > str(account["period_end"]):
            account["period_end"] = statement.statement_period_end.isoformat()
            account["last_document_id"] = document_id

    inventory = state.get("package_inventory", {})
    compact_inventory = {
        key: inventory.get(key)
        for key in (
            "total_documents",
            "total_pages",
            "extracted_documents",
            "failed_documents",
            "documents_by_kind",
            "bank_coverage_by_account",
            "missing_bank_months",
            "financial_years",
            "missing_core_kinds",
            "duplicate_document_ids",
            "complete",
        )
    }
    return json.dumps(
        {
            "bank_accounts": list(bank_accounts.values()),
            "package_cash_flow": state["ratios"].get("package_cash_flow", {}),
            "financial_trend": state["ratios"].get("financial_trend", {}),
            "package_inventory": compact_inventory,
            "tax_returns": tax_evidence(state),
            "tax_limitations": "Reported tax figures are not audited profit, proof of payment or verified repayment capacity. Cite the exact supplied chunk_id for tax facts.",
        },
        default=str,
    )


def _prompt_citations(
    state: AgentState, retrieval: RetrievalBundle, *, bank_limit: int = 5
) -> list[str]:
    candidates = {item.chunk_id for item in retrieval.evidence}
    candidates.update(item["chunk_id"] for item in tax_evidence(state))
    bank_metrics = state["ratios"].get("bank_statement_metrics", [])
    if len(bank_metrics) > bank_limit:
        indexes = {
            round(position * (len(bank_metrics) - 1) / (bank_limit - 1))
            for position in range(bank_limit)
        }
        bank_metrics = [metric for index, metric in enumerate(bank_metrics) if index in indexes]
    candidates.update(f"{metric['document_id']}:summary:0" for metric in bank_metrics)
    candidates.update(
        f"{ratio['document_id']}:period:0" for ratio in state["ratios"].get("financial_ratios", [])
    )
    for finding in state.get("inconsistencies", []):
        candidates.update(finding.get("citations", []))
    return sorted(candidates & state.get("citation_sources", {}).keys())


def _summary_retrieval(retrieval: RetrievalBundle) -> RetrievalBundle:
    structured_kinds = {"bank_statement", "audited_financials", "tax_return"}
    compact = retrieval.model_copy(deep=True)
    compact.evidence = [
        item for item in compact.evidence if item.document_kind not in structured_kinds
    ]
    return compact


def assess_5c_node(
    state: AgentState,
    *,
    llm: LLMProvider | None = None,
    store: VectorStore | None = None,
) -> dict[str, object]:
    """Step 5 — 5C credit assessment via structured LLM output."""
    started = _now()

    metrics, financial_ratios, inconsistencies = _assessment_evidence(state)

    retrieval = retrieve_evidence(state, store or VectorStore())
    retrieval.consumed_by = ["assess_5c"]
    allowed_chunk_ids = context_citations(state, retrieval)
    prompt_chunk_ids = _prompt_citations(state, retrieval)
    allowed_set = set(allowed_chunk_ids)
    prompt = build_five_c_prompt(
        metrics,
        inconsistencies,
        financial_ratios=financial_ratios,
        allowed_chunk_ids=prompt_chunk_ids,
        package_evidence=_package_evidence(state),
        retrieved_evidence=evidence_prompt(retrieval),
    )
    errors: list[AgentError] = [
        AgentError(node="assess_5c", message=warning) for warning in retrieval.warnings
    ]
    used_fallback = _all_uploaded_documents_failed(state)
    provider = None if used_fallback else (llm or get_llm())
    if used_fallback:
        used_fallback = True
        assessment = build_fallback_five_c(
            metrics,
            inconsistencies,
            financial_ratios,
            allowed_chunk_ids,
            package_cash_flow=state["ratios"].get("package_cash_flow"),
        )
    else:
        try:
            assessment = provider.generate_structured(prompt, FiveCAssessment)
        except Exception as error:
            used_fallback = True
            assessment = build_fallback_five_c(
                metrics,
                inconsistencies,
                financial_ratios,
                allowed_chunk_ids,
                package_cash_flow=state["ratios"].get("package_cash_flow"),
            )
            errors.append(
                AgentError(
                    node="assess_5c",
                    message=f"LLM unavailable; used deterministic 5C fallback: {_brief_error(error)}",
                    recoverable=True,
                )
            )
    invalid = _five_c_invalid_citations(assessment, allowed_set)
    if invalid and not used_fallback:
        assessment = provider.generate_structured(
            prompt
            + "\n\nCORRECTION REQUIRED: The previous response used invalid evidence_chunk_ids: "
            + ", ".join(invalid)
            + ". Regenerate the full assessment using only exact ids from Allowed chunk_ids.",
            FiveCAssessment,
        )
        invalid = _five_c_invalid_citations(assessment, allowed_set)

    if invalid:
        _filter_five_c_citations(assessment, allowed_set)
        errors.append(
            AgentError(
                node="assess_5c",
                message=(f"Removed unverifiable 5C evidence chunk_ids after one retry: {invalid}."),
                recoverable=True,
            )
        )

    citations: list[str] = []
    if not financial_ratios or all(ratio.dsr.value is None for ratio in financial_ratios):
        assessment.capacity.rating = type(assessment.capacity.rating)("insufficient_data")
        assessment.capacity.reasoning = (
            (
                "Available bank or financial metrics provide partial evidence, not verified debt-servicing capacity. "
                if metrics or financial_ratios
                else "No bank or audited financial metrics are available to verify debt-servicing capacity. "
            )
            + "Without verified repayment obligations, this prototype does not assign a capacity strength rating. "
            "Missing evidence is not evidence of weakness."
        )
        if financial_ratios:
            assessment.capacity.reasoning += " " + " ".join(
                f"For FY {ratio.period_end}, reported cash from operations is RM{ratio.inputs.get('cash_from_operations', 'unavailable')}, "
                f"EBIT is RM{ratio.inputs.get('ebit', 'unavailable')} and interest coverage is {ratio.interest_coverage.value}."
                for ratio in financial_ratios
            )
            assessment.capacity.evidence_chunk_ids = list(
                dict.fromkeys(
                    [
                        *assessment.capacity.evidence_chunk_ids,
                        *[
                            f"{ratio.document_id}:period:0"
                            for ratio in financial_ratios
                            if f"{ratio.document_id}:period:0" in allowed_set
                        ],
                    ]
                )
            )
        assessment.capacity.flags_for_human_review = list(
            dict.fromkeys(
                [
                    *assessment.capacity.flags_for_human_review,
                    (
                        "Verify existing and proposed repayment obligations against the actual repayment schedule."
                        if financial_ratios
                        else "Obtain financial statements and verify existing and proposed repayment obligations."
                    ),
                ]
            )
        )
    if state.get("package_inventory", {}).get("missing_bank_months") or not metrics:
        assessment.character.rating = type(assessment.character.rating)("insufficient_data")
        bank_evidence_limitation = (
            "Limited bank activity is an observation, not proof of reliable repayment behaviour. "
            if metrics
            else "No bank-activity evidence is available to assess payment conduct or repayment behaviour. "
        )
        supplied_compliance_documents: list[str] = []
        if state.get("ssm_registrations"):
            supplied_compliance_documents.append("SSM registration")
        if state.get("tax_returns"):
            supplied_compliance_documents.append("a tax return")
        compliance_limitation = ""
        if supplied_compliance_documents:
            document_phrase = " and ".join(supplied_compliance_documents)
            verb = "does" if len(supplied_compliance_documents) == 1 else "do"
            compliance_limitation = (
                f"{document_phrase} alone {verb} not verify current legal compliance, "
                "tax filing acceptance or tax payment. "
            )
        assessment.character.reasoning = (
            "The supplied documents do not establish sustained payment conduct across the configured review period. "
            + bank_evidence_limitation
            + compliance_limitation
            + "Missing evidence is not evidence of poor character."
        )
        character_checks = ["Review the missing banking history"]
        if state.get("ssm_registrations"):
            character_checks.append("independently verify registration status")
        if state.get("tax_returns"):
            character_checks.append("verify tax filing acceptance and payment records")
        assessment.character.flags_for_human_review.append("; ".join(character_checks) + ".")
    concentration_percentages, concentration_citations = _high_management_concentration(retrieval)
    if concentration_percentages:
        assessment.conditions.rating = type(assessment.conditions.rating)("weak")
        formatted_percentages = " and ".join(
            f"{percentage:g}%" for percentage in concentration_percentages
        )
        assessment.conditions.reasoning = (
            "Retrieved management accounts report customer or supplier concentration of "
            f"{formatted_percentages}. This prototype treats concentration at or above 50% "
            "as a material dependency-risk flag requiring human review, so Conditions cannot "
            "be rated adequate from the supplied package."
        )
        assessment.conditions.evidence_chunk_ids = list(
            dict.fromkeys(
                [
                    *assessment.conditions.evidence_chunk_ids,
                    *[citation for citation in concentration_citations if citation in allowed_set],
                ]
            )
        )
        assessment.conditions.flags_for_human_review = list(
            dict.fromkeys(
                [
                    *assessment.conditions.flags_for_human_review,
                    "Review customer and supplier concentration and verify mitigation or alternative counterparties.",
                ]
            )
        )
    assessment.character.flags_for_human_review = list(
        dict.fromkeys(
            [
                *assessment.character.flags_for_human_review,
                *retrieval.warnings,
                *[
                    f"{finding.code}: {finding.message}"
                    for finding in inconsistencies
                    if finding.severity.value != "info"
                ],
            ]
        )
    )
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
        inputs={
            "metric_sets": len(metrics),
            "inconsistencies": len(inconsistencies),
            "retrieved_chunks": len(retrieval.evidence),
            "embedding_space": retrieval.embedding_space,
        },
        outputs=assessment.model_dump(mode="json"),
        citations=sorted(set(citations)),
    )
    return {
        "five_c": assessment.model_dump(mode="json"),
        "retrieval": retrieval.model_dump(mode="json"),
        "trace": [step],
        "errors": errors,
    }


def summarise_node(
    state: AgentState,
    *,
    llm: LLMProvider | None = None,
) -> dict[str, object]:
    """Step 6 — produce a source-traced natural-language risk summary."""
    started = _now()
    five_c_payload = state.get("five_c", {})
    if not five_c_payload:
        raise ValueError("summarise_node requires five_c output from assess_5c_node")
    five_c = FiveCAssessment.model_validate(five_c_payload)

    metrics, financial_ratios, inconsistencies = _assessment_evidence(state)

    retrieval = RetrievalBundle.model_validate(state["retrieval"])
    if retrieval.application_id != state.get("application_id"):
        raise ValueError("Summary retrieval evidence belongs to a different application")
    retrieval.consumed_by = list(dict.fromkeys([*retrieval.consumed_by, "summarise"]))
    allowed_chunk_ids = context_citations(state, retrieval)
    summary_retrieval = _summary_retrieval(retrieval)
    prompt_chunk_ids = _prompt_citations(state, summary_retrieval, bank_limit=3)
    prompt_chunk_ids = sorted(
        set(prompt_chunk_ids).union(
            *(
                set(dimension.evidence_chunk_ids[:3])
                for dimension in (
                    five_c.character,
                    five_c.capacity,
                    five_c.capital,
                    five_c.collateral,
                    five_c.conditions,
                )
            )
        )
        & set(allowed_chunk_ids)
    )
    allowed_set = set(allowed_chunk_ids)

    prompt = build_summary_prompt(
        metrics,
        inconsistencies,
        five_c,
        prompt_chunk_ids,
        financial_ratios=financial_ratios,
        package_evidence=_package_evidence(state),
        retrieved_evidence=evidence_prompt(summary_retrieval),
    )
    errors: list[AgentError] = []
    used_fallback = _all_uploaded_documents_failed(state)
    provider = None if used_fallback else (llm or get_llm())
    if used_fallback:
        summary = build_fallback_summary(
            metrics,
            inconsistencies,
            five_c,
            financial_ratios,
            allowed_chunk_ids,
            package_cash_flow=state["ratios"].get("package_cash_flow"),
            package_inventory=state.get("package_inventory"),
            needs_ocr_pages=state.get("needs_ocr_pages"),
            document_parse_failures=state.get("document_parse_failures"),
        )
    else:
        try:
            summary = provider.generate_structured(prompt, RiskSummary)
        except Exception as error:
            used_fallback = True
            summary = build_fallback_summary(
                metrics,
                inconsistencies,
                five_c,
                financial_ratios,
                allowed_chunk_ids,
                package_cash_flow=state["ratios"].get("package_cash_flow"),
                package_inventory=state.get("package_inventory"),
                needs_ocr_pages=state.get("needs_ocr_pages"),
                document_parse_failures=state.get("document_parse_failures"),
            )
            errors.append(
                AgentError(
                    node="summarise",
                    message=f"LLM unavailable; used deterministic summary fallback: {_brief_error(error)}",
                    recoverable=True,
                )
            )

    summary.headline = normalise_inventory_headline_citations(summary.headline)

    # Verify every cited chunk_id is real. We don't re-prompt the LLM —
    # we surface the discrepancy as a recoverable error so the dashboard
    # can show the loan officer that the AI cited something unverifiable.
    cited = set(extract_citations(summary.headline) + extract_citations(summary.body))
    summary.cited_chunk_ids = sorted(cited)
    invalid = sorted(cited - allowed_set)
    if invalid and not used_fallback:
        summary = provider.generate_structured(
            prompt
            + "\n\nCORRECTION REQUIRED: The previous response used invalid citations: "
            + ", ".join(invalid)
            + ". Regenerate the full summary using only exact ids from Allowed chunk_ids.",
            RiskSummary,
        )
        summary.headline = normalise_inventory_headline_citations(summary.headline)
        cited = set(extract_citations(summary.headline) + extract_citations(summary.body))
        invalid = sorted(cited - allowed_set)

    if has_unsupported_critical_label(summary, inconsistencies):
        summary = build_fallback_summary(
            metrics,
            inconsistencies,
            five_c,
            financial_ratios,
            allowed_chunk_ids,
            package_cash_flow=state["ratios"].get("package_cash_flow"),
            package_inventory=state.get("package_inventory"),
            needs_ocr_pages=state.get("needs_ocr_pages"),
            document_parse_failures=state.get("document_parse_failures"),
        )
        cited = set(extract_citations(summary.headline) + extract_citations(summary.body))
        invalid = sorted(cited - allowed_set)
        errors.append(
            AgentError(
                node="summarise",
                message="Unsupported critical severity in AI summary; used deterministic summary fallback. Review structured validation findings.",
                recoverable=True,
            )
        )

    if invalid:
        summary = build_fallback_summary(
            metrics,
            inconsistencies,
            five_c,
            financial_ratios,
            allowed_chunk_ids,
            package_cash_flow=state["ratios"].get("package_cash_flow"),
            package_inventory=state.get("package_inventory"),
            needs_ocr_pages=state.get("needs_ocr_pages"),
            document_parse_failures=state.get("document_parse_failures"),
        )
        cited = set(extract_citations(summary.headline) + extract_citations(summary.body))
        errors.append(
            AgentError(
                node="summarise",
                message=(
                    f"Unverifiable summary citations after one retry: {invalid}. "
                    "Replaced AI narrative with deterministic fallback; human review remains required."
                ),
                recoverable=True,
            )
        )
    required_checks = [finding for finding in inconsistencies if finding.severity.value != "info"]
    summary.recommended_human_checks = _clean_human_checks(
        [*summary.recommended_human_checks, *retrieval.warnings],
        {finding.code for finding in required_checks},
    )
    missing_checks = [finding for finding in required_checks if finding.code not in summary.body]
    if missing_checks:
        lines = []
        for finding in missing_checks:
            source_tags = " ".join(
                f"[{citation}]"
                for citation in dict.fromkeys(finding.citations)
                if citation in allowed_set
            )
            basis = source_tags or "(package inventory check)"
            lines.append(
                f"{finding.code} ({finding.severity.value.upper()}): {finding.message} {basis}"
            )
        summary.body += "\n\nSystem validation checks:\n" + "\n".join(lines)
    cited = set(extract_citations(summary.headline) + extract_citations(summary.body))
    summary.cited_chunk_ids = sorted(cited & allowed_set)

    step = ReasoningStep(
        node="summarise",
        started_at=started,
        finished_at=_now(),
        summary=f"Generated risk summary with {len(cited)} citation(s)",
        inputs={
            "allowed_citations": len(allowed_chunk_ids),
            "retrieved_chunks": len(retrieval.evidence),
        },
        outputs={"cited": sorted(cited), "invalid_citations": invalid},
        citations=sorted(cited & allowed_set),
    )
    return {
        "risk_summary": summary.model_dump_json(),
        "retrieval": retrieval.model_dump(mode="json"),
        "trace": [step],
        "errors": errors,
    }


def _by_severity(inconsistencies: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in inconsistencies:
        sev = issue.severity.value
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def _brief_error(error: Exception) -> str:
    message = str(error) or type(error).__name__
    if "RESOURCE_EXHAUSTED" in message or "429" in message:
        return "LLM provider rate limit or quota exhausted"
    return message.splitlines()[0][:200]
