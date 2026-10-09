"""Application-analysis HTTP routes.

A loan officer uploads N PDFs at once (a full SME application package).
The graph runs to completion and returns the final state in a single
response — `Sync 1 request, 30s loading` per the Phase 5 design choice.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
import threading
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import quote

import pymupdf
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.agent.graph import compile_graph
from app.agent.retrieval import tax_evidence
from app.agent.state import ReasoningStep
from app.api.history import save_record
from app.core.config import settings
from app.core.provenance import source_fingerprint
from app.ingestion.source_documents import SourceDocuments
from app.ingestion.store import VectorStore

router = APIRouter()
MAX_FILES = 50
MAX_TOTAL_BYTES = 100 * 1024 * 1024


class TraceItem(BaseModel):
    node: str
    duration_ms: float
    summary: str


class AnalysisResponse(BaseModel):
    tax_returns: list[dict[str, Any]] = Field(default_factory=list)
    application_id: str
    document_ids: list[str]
    document_kinds: dict[str, str]
    needs_ocr_pages: dict[str, list[int]] = {}
    inconsistencies: list[dict[str, Any]] = []
    ratios: dict[str, Any] = {}
    five_c: dict[str, Any] = {}
    risk_summary: dict[str, Any] | None = None
    trace: list[TraceItem] = []
    errors: list[dict[str, Any]] = []
    package_inventory: dict[str, Any] = {}
    citation_sources: dict[str, dict[str, Any]] = Field(default_factory=dict)
    retrieval: dict[str, Any] = Field(default_factory=dict)


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    phase: str
    result: AnalysisResponse | None = None
    error: str | None = None


_jobs: dict[str, AnalysisJobResponse] = {}
_jobs_lock = threading.Lock()


def _trace_payload(trace: list[ReasoningStep]) -> list[TraceItem]:
    return [
        TraceItem(
            node=step.node,
            duration_ms=(step.finished_at - step.started_at).total_seconds() * 1000,
            summary=step.summary,
        )
        for step in trace
    ]


def _validate_uploads(files: list[UploadFile]) -> None:
    if not files:
        raise HTTPException(400, "Upload at least one PDF")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"A package may contain at most {MAX_FILES} PDFs")
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"Only .pdf uploads are supported: {file.filename}")


def _save_uploads(files: list[UploadFile], target_dir: Path) -> list[str]:
    paths: list[str] = []
    total_bytes = 0
    for index, upload in enumerate(files, start=1):
        safe_name = Path(upload.filename or f"document_{index}.pdf").name
        target = target_dir / f"{index:03d}_{safe_name}"
        with target.open("wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
        total_bytes += target.stat().st_size
        if total_bytes > MAX_TOTAL_BYTES:
            raise HTTPException(413, "Uploaded package exceeds the 100 MB limit")
        paths.append(str(target))
    return paths


def _update_job_progress(application_id: str, progress: int, phase: str) -> None:
    with _jobs_lock:
        job = _jobs.get(application_id)
        if job is not None and job.status == JobStatus.PROCESSING:
            _jobs[application_id] = job.model_copy(update={"progress": max(job.progress, progress), "phase": phase})


def _execute_analysis_graph(application_id: str, pdf_paths: list[str]) -> AnalysisResponse:
    graph = compile_graph()
    thread_config = {"configurable": {"thread_id": application_id}}
    stages = {"parse": (20, "extracting"), "extract": (40, "validating"),
              "validate": (50, "calculating"), "ratios": (55, "assessing"),
              "assess_5c": (80, "summarising"), "summarise": (95, "saving")}
    state = {}
    for state in graph.stream(
        {
            "application_id": application_id,
            "pdf_paths": pdf_paths,
            "original_filenames": {
                path: re.sub(r"^\d{3}_", "", Path(path).name) for path in pdf_paths
            },
            "trace": [],
            "errors": [],
        },
        config=thread_config,
        stream_mode="values",
    ):
        trace = state.get("trace", [])
        if trace and trace[-1].node in stages:
            _update_job_progress(application_id, *stages[trace[-1].node])
    risk_summary_payload: dict[str, Any] | None = None
    if state.get("risk_summary"):
        risk_summary_payload = json.loads(state["risk_summary"])
    source_documents = SourceDocuments()
    for document_id, path in state.get("document_paths", {}).items():
        source_documents.archive(document_id, Path(path), state["document_filenames"][document_id])
    cited_ids = set((risk_summary_payload or {}).get("cited_chunk_ids", []))
    taxes = tax_evidence(state)
    cited_ids.update(item["chunk_id"] for item in taxes)
    for dimension in state.get("five_c", {}).values():
        cited_ids.update(dimension.get("evidence_chunk_ids", []))
    for finding in state.get("inconsistencies", []):
        cited_ids.update(finding.get("citations", []))
    for evidence in state.get("retrieval", {}).get("evidence", []):
        cited_ids.add(evidence["chunk_id"])
    return AnalysisResponse(
        tax_returns=taxes,
        application_id=application_id,
        document_ids=state.get("document_ids", []),
        document_kinds={
            document_id: kind.value for document_id, kind in state.get("document_kinds", {}).items()
        },
        needs_ocr_pages=state.get("needs_ocr_pages", {}),
        inconsistencies=state.get("inconsistencies", []),
        ratios=state.get("ratios", {}),
        five_c=state.get("five_c", {}),
        risk_summary=risk_summary_payload,
        trace=_trace_payload(state.get("trace", [])),
        errors=[
            {"node": error.node, "message": error.message, "recoverable": error.recoverable}
            for error in state.get("errors", [])
        ],
        package_inventory=state.get("package_inventory", {}),
        retrieval=state.get("retrieval", {}),
        citation_sources={
            chunk_id: reference
            for chunk_id, reference in state.get("citation_sources", {}).items()
            if chunk_id in cited_ids
        },
    )


def _execute_analysis(application_id: str, pdf_paths: list[str]) -> AnalysisResponse:
    started_at = datetime.now(UTC).isoformat()
    started = perf_counter()
    result = None
    failed = False
    try:
        result = _execute_analysis_graph(application_id, pdf_paths)
        return result
    except Exception:
        failed = True
        raise
    finally:
        record = {
            "category": "analysis",
            "origin": "automatic",
            "title": f"Analysis {application_id[:8]}",
            "status": "failed" if failed else "completed",
            "application_id": application_id,
            "started_at": started_at,
            "duration_seconds": round(perf_counter() - started, 3),
            "document_count": len(pdf_paths),
            "version": settings.app_version,
            "configuration": {
                "backend_source_sha256": source_fingerprint(),
                "model": (
                    settings.gemini_model
                    if settings.llm_provider == "gemini"
                    else settings.groq_model if settings.llm_provider == "groq" else None
                ),
                "llm_provider": settings.llm_provider,
                "gemini_model": settings.gemini_model if settings.llm_provider == "gemini" else None,
                "groq_model": settings.groq_model if settings.llm_provider == "groq" else None,
                "embeddings_provider": settings.embeddings_provider,
                "rag_score_threshold": settings.rag_score_threshold,
                "rag_results_per_query": settings.rag_results_per_query,
            },
            "details": "Execution failed; inspect backend logs." if failed else "Processing finished. Conclusions still require human verification.",
            "result": result.model_dump(mode="json") if result else None,
        }
        try:
            save_record(record)
        except Exception:
            logging.getLogger(__name__).exception("Could not persist development history for %s", application_id)
            if result is not None:
                result.errors.append({"node": "history", "message": "Development history could not be saved.", "recoverable": True})


@router.post("/analyse", response_model=AnalysisResponse)
async def analyse(files: list[UploadFile] = File(...)) -> AnalysisResponse:
    """Run the full credit-assessment graph against an uploaded package.

    Each PDF is detected, extracted, validated, ratio-analysed, 5C-rated,
    and summarised with inline citations. The response is the same shape
    as the agent's terminal state, plus a duration-stamped trace.
    """
    _validate_uploads(files)

    application_id = str(uuid.uuid4())
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"fyp_app_{application_id[:8]}_"))
    pdf_paths: list[str] = []
    try:
        pdf_paths = _save_uploads(files, tmp_dir)
        return _execute_analysis(application_id, pdf_paths)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _run_analysis_job(job_id: str, tmp_dir: Path, pdf_paths: list[str]) -> None:
    with _jobs_lock:
        _jobs[job_id] = AnalysisJobResponse(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            progress=10,
            phase="reading",
        )
    try:
        result = _execute_analysis(job_id, pdf_paths)
        response = AnalysisJobResponse(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            phase="completed",
            result=result,
        )
    except Exception as error:
        with _jobs_lock:
            last_progress = _jobs[job_id].progress
        response = AnalysisJobResponse(
            job_id=job_id,
            status=JobStatus.FAILED,
            progress=last_progress,
            phase="failed",
            error=str(error),
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    with _jobs_lock:
        _jobs[job_id] = response


@router.post("/analyse/jobs", response_model=AnalysisJobResponse)
async def start_analysis_job(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
) -> AnalysisJobResponse:
    _validate_uploads(files)
    job_id = str(uuid.uuid4())
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"fyp_job_{job_id[:8]}_"))
    try:
        pdf_paths = _save_uploads(files, tmp_dir)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    queued = AnalysisJobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        progress=5,
        phase="queued",
    )
    with _jobs_lock:
        _jobs[job_id] = queued
    background_tasks.add_task(_run_analysis_job, job_id, tmp_dir, pdf_paths)
    return queued


@router.get("/analyse/jobs/{job_id}", response_model=AnalysisJobResponse)
async def get_analysis_job(job_id: str) -> AnalysisJobResponse:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Analysis job not found")
    return job


@router.get("/chunks/{document_id:path}/{kind}/{index}")
async def get_chunk(
    document_id: str, kind: str, index: int, application_id: str | None = None
) -> dict[str, Any]:
    """Resolve a chunk_id back to its source text and metadata.

    Used by the frontend when the user clicks an inline citation. The
    `document_id:path` converter keeps slashes in the id intact.
    """
    chunk_id = f"{document_id}:{kind}:{index}"
    store = VectorStore()
    hit = (
        store.get_chunk(chunk_id, application_id=application_id)
        if application_id is not None
        else store.get_chunk(chunk_id)
    )
    if hit is None:
        raise HTTPException(404, f"chunk {chunk_id} not found")
    source = SourceDocuments().lookup(hit.document_id)
    encoded_id = quote(hit.document_id, safe="/")
    return {
        "chunk_id": hit.chunk_id,
        "document_id": hit.document_id,
        "kind": hit.kind,
        "text": hit.text,
        "page": hit.page,
        "source_metadata": hit.source_metadata,
        "filename": source[1] if source else hit.source_metadata.get("filename", hit.document_id),
        "source_pages": hit.source_metadata.get("source_pages", []),
        "source_locations": hit.source_metadata.get("source_locations", []),
        "pdf_url": f"/api/applications/source-pdfs/{encoded_id}" if source else None,
        "preview_url": f"/api/applications/source-pages/{encoded_id}" if source else None,
    }


@router.get("/source-pdfs/{document_id:path}")
async def get_source_pdf(document_id: str) -> FileResponse:
    source = SourceDocuments().lookup(document_id)
    if source is None:
        raise HTTPException(
            404, "Original PDF unavailable. Re-upload this package to preserve its sources."
        )
    return FileResponse(
        source[0],
        media_type="application/pdf",
        filename=source[1],
        content_disposition_type="inline",
        headers={"Cache-Control": "private"},
    )


@router.get("/source-pages/{document_id:path}/{page}")
async def get_source_page(document_id: str, page: int) -> Response:
    source = SourceDocuments().lookup(document_id)
    if source is None:
        raise HTTPException(404, "Original PDF unavailable")
    with pymupdf.open(source[0]) as document:
        if page < 1 or page > len(document):
            raise HTTPException(404, "Source page not found")
        content = document[page - 1].get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4)).tobytes("png")
    return Response(content=content, media_type="image/png", headers={"Cache-Control": "private"})
