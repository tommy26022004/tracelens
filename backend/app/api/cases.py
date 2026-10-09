import json
from datetime import UTC, datetime
from threading import RLock
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.history import get_history
from app.core.config import settings

router = APIRouter()
lock = RLock()


class CaseInput(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    reference: str = Field(default="", max_length=100)
    environment: Literal["test", "real"] = "test"


class CaseUpdate(BaseModel):
    status: Literal["under_review", "awaiting_documents", "reviewed"]
    note: str = Field(default="", max_length=6000)
    run_id: UUID | None = None


def directory():
    return settings.source_documents_dir.parent / "company_cases"


def write_case(record):
    directory().mkdir(parents=True, exist_ok=True)
    target = directory() / f"{record['id']}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
    return record


@router.get("")
def list_cases():
    with lock:
        records = [json.loads(path.read_text(encoding="utf-8")) for path in directory().glob("*.json")]
    return {"items": sorted(records, key=lambda item: item["updated_at"], reverse=True)}


@router.post("", status_code=201)
def create_case(payload: CaseInput):
    if not payload.company.strip():
        raise HTTPException(422, "Company name is required")
    now = datetime.now(UTC).isoformat()
    with lock:
        return write_case({**payload.model_dump(), "company": payload.company.strip(), "id": str(uuid4()),
                           "created_at": now, "updated_at": now, "status": "under_review", "runs": [], "events": []})


@router.post("/{case_id}/updates")
def update_case(case_id: UUID, payload: CaseUpdate):
    with lock:
        path = directory() / f"{case_id}.json"
        if not path.exists():
            raise HTTPException(404, "Case not found")
        record = json.loads(path.read_text(encoding="utf-8"))
        run = None
        if payload.run_id:
            run = get_history(str(payload.run_id))
            if run.get("category") != "analysis" or not run.get("result"):
                raise HTTPException(422, "Only saved analysis results can be linked")
            if str(payload.run_id) in [item["id"] for item in record["runs"]]:
                raise HTTPException(409, "This analysis is already linked")
        now = datetime.now(UTC).isoformat()
        record["events"].append({"at": now, "previous_status": record["status"], "status": payload.status,
                                  "note": payload.note.strip(), "run_id": str(payload.run_id) if payload.run_id else None})
        record["status"] = payload.status
        record["updated_at"] = now
        if run:
            record["runs"].append({"id": run["id"], "application_id": run["application_id"],
                                    "created_at": run["created_at"], "document_count": run.get("document_count", 0)})
        return write_case(record)
