"""Application-analysis HTTP routes.

A loan officer uploads N PDFs at once (a full SME application package).
The graph runs to completion and returns the final state in a single
response — `Sync 1 request, 30s loading` per the Phase 5 design choice.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.agent.graph import compile_graph
from app.agent.state import ReasoningStep
from app.ingestion.store import VectorStore

router = APIRouter()


class TraceItem(BaseModel):
    node: str
    duration_ms: float
    summary: str


class AnalysisResponse(BaseModel):
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


def _trace_payload(trace: list[ReasoningStep]) -> list[TraceItem]:
    return [
        TraceItem(
            node=step.node,
            duration_ms=(step.finished_at - step.started_at).total_seconds() * 1000,
            summary=step.summary,
        )
        for step in trace
    ]


@router.post("/analyse", response_model=AnalysisResponse)
async def analyse(files: list[UploadFile] = File(...)) -> AnalysisResponse:
    """Run the full credit-assessment graph against an uploaded package.

    Each PDF is detected, extracted, validated, ratio-analysed, 5C-rated,
    and summarised with inline citations. The response is the same shape
    as the agent's terminal state, plus a duration-stamped trace.
    """
    if not files:
        raise HTTPException(400, "Upload at least one PDF")
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"Only .pdf uploads are supported: {file.filename}")

    application_id = str(uuid.uuid4())
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"fyp_app_{application_id[:8]}_"))
    pdf_paths: list[str] = []
    try:
        for upload in files:
            target = tmp_dir / (upload.filename or f"{uuid.uuid4()}.pdf")
            with target.open("wb") as buf:
                shutil.copyfileobj(upload.file, buf)
            pdf_paths.append(str(target))

        graph = compile_graph()
        thread_config = {"configurable": {"thread_id": application_id}}
        state = graph.invoke(
            {
                "application_id": application_id,
                "pdf_paths": pdf_paths,
                "trace": [],
                "errors": [],
            },
            config=thread_config,
        )

        risk_summary_payload: dict[str, Any] | None = None
        if state.get("risk_summary"):
            risk_summary_payload = json.loads(state["risk_summary"])

        return AnalysisResponse(
            application_id=application_id,
            document_ids=state.get("document_ids", []),
            document_kinds={
                doc_id: kind.value
                for doc_id, kind in state.get("document_kinds", {}).items()
            },
            needs_ocr_pages=state.get("needs_ocr_pages", {}),
            inconsistencies=state.get("inconsistencies", []),
            ratios=state.get("ratios", {}),
            five_c=state.get("five_c", {}),
            risk_summary=risk_summary_payload,
            trace=_trace_payload(state.get("trace", [])),
            errors=[
                {"node": e.node, "message": e.message, "recoverable": e.recoverable}
                for e in state.get("errors", [])
            ],
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/chunks/{document_id:path}/{kind}/{index}")
async def get_chunk(document_id: str, kind: str, index: int) -> dict[str, Any]:
    """Resolve a chunk_id back to its source text and metadata.

    Used by the frontend when the user clicks an inline citation. The
    `document_id:path` converter keeps slashes in the id intact.
    """
    chunk_id = f"{document_id}:{kind}:{index}"
    store = VectorStore()
    hits = store.semantic_search(chunk_id, limit=25)
    for hit in hits:
        if hit.chunk_id == chunk_id:
            return {
                "chunk_id": hit.chunk_id,
                "document_id": hit.document_id,
                "kind": hit.kind,
                "text": hit.text,
                "page": hit.page,
                "source_metadata": hit.source_metadata,
            }
    raise HTTPException(404, f"chunk {chunk_id} not found")
