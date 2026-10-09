"""Document HTTP routes."""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.ingestion.pipeline import IngestionResult, ingest_bank_statement
from app.ingestion.store import VectorStore

router = APIRouter()


@router.post("/ingest", response_model=IngestionResult)
async def ingest(file: UploadFile = File(...)) -> IngestionResult:
    """Parse → extract → chunk → embed → upsert into Qdrant.

    Returns the document id needed for subsequent semantic search and the
    structured ingestion summary (counts + OCR-needed page list).
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only .pdf uploads are supported")

    tmp_dir = Path(tempfile.mkdtemp(prefix="fyp_ingest_"))
    tmp_path = tmp_dir / f"{uuid.uuid4()}.pdf"
    try:
        with tmp_path.open("wb") as buf:
            shutil.copyfileobj(file.file, buf)
        result, _ = ingest_bank_statement(tmp_path)
        return result
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    application_id: str = Query(..., min_length=1),
    document_id: str | None = None,
    kind: str | None = Query(None, pattern="^(summary|transaction|period|director|page)$"),
    limit: int = Query(5, ge=1, le=25),
) -> dict[str, list[dict[str, object]]]:
    """Semantic search over ingested chunks. Used by the agent in Phase 3."""
    store = VectorStore()
    hits = store.semantic_search(
        q, application_id=application_id, limit=limit, document_id=document_id, kind=kind
    )
    return {
        "hits": [
            {
                "chunk_id": h.chunk_id,
                "document_id": h.document_id,
                "kind": h.kind,
                "text": h.text,
                "page": h.page,
                "score": h.score,
                "source_metadata": h.source_metadata,
            }
            for h in hits
        ]
    }
