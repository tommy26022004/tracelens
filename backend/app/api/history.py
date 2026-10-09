import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import settings

router = APIRouter()


class HistoryInput(BaseModel):
    category: Literal["test", "bug", "note"]
    title: str = Field(min_length=1, max_length=200)
    status: Literal["not_run", "passed", "failed", "open", "resolved", "recorded"]
    details: str = Field(default="", max_length=20000)
    evidence: str = Field(default="", max_length=4000)
    related_id: str = Field(default="", max_length=100)
    version: str = Field(default="", max_length=200)
    expected: str = Field(default="", max_length=6000)
    actual: str = Field(default="", max_length=6000)
    improvement: str = Field(default="", max_length=6000)


def history_directory() -> Path:
    return settings.source_documents_dir.parent / "development_history"


def save_record(payload: dict) -> dict:
    record = {
        **payload,
        "id": str(uuid4()),
        "created_at": datetime.now(UTC).isoformat(),
    }
    directory = history_directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{record['id']}.json"
    temporary = target.with_suffix(".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, allow_nan=False)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return record


def read_records() -> list[dict]:
    directory = history_directory()
    if not directory.exists():
        return []
    records = []
    for path in directory.glob("*.json"):
        with path.open(encoding="utf-8") as stream:
            records.append(json.load(stream))
    return sorted(records, key=lambda record: record["created_at"], reverse=True)


@router.get("")
def list_history(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)) -> dict:
    try:
        records = read_records()
    except (OSError, ValueError) as error:
        raise HTTPException(503, "History could not be read; existing records were not modified") from error
    return {"items": [{key: value for key, value in record.items() if key != "result"}
                      for record in records[offset:offset + limit]], "total": len(records)}


@router.post("", status_code=201)
def create_history(entry: HistoryInput) -> dict:
    allowed = {"test": {"not_run", "passed", "failed"}, "bug": {"open", "resolved"}, "note": {"recorded"}}
    if not entry.title.strip() or entry.status not in allowed[entry.category]:
        raise HTTPException(422, "Title and status must match the entry category")
    try:
        return save_record({**entry.model_dump(), "title": entry.title.strip(), "origin": "manual"})
    except OSError as error:
        raise HTTPException(503, "History was not saved; please retry") from error


@router.get("/{record_id}")
def get_history(record_id: str) -> dict:
    try:
        canonical_id = str(UUID(record_id))
    except ValueError as error:
        raise HTTPException(404, "History record not found") from error
    path = history_directory() / f"{canonical_id}.json"
    if not path.exists():
        raise HTTPException(404, "History record not found")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise HTTPException(503, "History record could not be read") from error
