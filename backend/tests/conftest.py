from __future__ import annotations

import pytest

from app.api import applications


class MemoryJobStore:
    """Test double; production always uses Redis/PostgreSQL."""

    def __init__(self) -> None:
        self.payloads: dict[str, str] = {}

    def put(self, job_id: str, payload: str) -> None:
        self.payloads[job_id] = payload

    def get(self, job_id: str) -> str | None:
        return self.payloads.get(job_id)


@pytest.fixture(autouse=True)
def memory_job_store(monkeypatch):
    store = MemoryJobStore()
    monkeypatch.setattr(applications, "_job_store", store)
    return store
