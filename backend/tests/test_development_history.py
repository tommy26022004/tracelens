import pytest
from fastapi.testclient import TestClient

from app.api import applications, history
from app.core.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "source_documents_dir", tmp_path / "sources")
    return TestClient(app)


def test_empty_history_and_manual_persistence(client):
    assert client.get("/api/history").json() == {"items": [], "total": 0}
    response = client.post("/api/history", json={"category": "test", "status": "not_run", "title": "First test"})
    assert response.status_code == 201
    record = response.json()
    assert record["origin"] == "manual"
    assert (history.history_directory() / f"{record['id']}.json").exists()
    assert TestClient(app).get(f"/api/history/{record['id']}").json() == record
    assert client.get("/api/history").json()["total"] == 1


def test_reject_invalid_status_and_blank_title(client):
    for payload in [
        {"category": "bug", "status": "passed", "title": "Bug"},
        {"category": "test", "status": "passed", "title": "   "},
        {"category": "analysis", "status": "passed", "title": "Fake automatic run"},
    ]:
        assert client.post("/api/history", json=payload).status_code == 422
    assert client.get("/api/history").json()["total"] == 0
    assert client.get("/api/history/not-an-id").status_code == 404


def test_structured_follow_up_preserves_original(client):
    original = client.post("/api/history", json={"category": "bug", "status": "open", "title": "Inclusive days"}).json()
    payload = {"category": "test", "status": "passed", "title": "Retest", "related_id": original["id"],
               "expected": "31 days", "actual": "31 days", "improvement": "Inclusive date calculation"}
    response = client.post("/api/history", json=payload)
    assert response.status_code == 201
    for field, value in payload.items():
        assert response.json()[field] == value
    assert client.get(f"/api/history/{original['id']}").json() == original


def test_analysis_snapshot_and_failure(client, monkeypatch):
    def execute(application_id, paths):
        return applications.AnalysisResponse(application_id=application_id, document_ids=[], document_kinds={})

    monkeypatch.setattr(applications, "_execute_analysis_graph", execute)
    applications._execute_analysis("test-run", ["test.pdf"])
    entry = client.get("/api/history").json()["items"][0]
    assert entry["status"] == "completed"
    assert len(entry["configuration"]["backend_source_sha256"]) == 64
    assert "result" not in entry
    assert client.get(f"/api/history/{entry['id']}").json()["result"]["application_id"] == "test-run"

    def fail(application_id, paths):
        raise RuntimeError("private error text")

    monkeypatch.setattr(applications, "_execute_analysis_graph", fail)
    with pytest.raises(RuntimeError):
        applications._execute_analysis("failed-run", [])
    records = history.read_records()
    assert records[0]["status"] == "failed"
    assert "private error text" not in records[0]["details"]


def test_storage_failure_does_not_destroy_analysis(client, monkeypatch):
    monkeypatch.setattr(applications, "_execute_analysis_graph", lambda application_id, paths:
                        applications.AnalysisResponse(application_id=application_id, document_ids=[], document_kinds={}))

    def fail(payload):
        raise OSError("disk full")

    monkeypatch.setattr(applications, "save_record", fail)
    result = applications._execute_analysis("run", [])
    assert result.errors[0]["node"] == "history"


def test_corrupt_record_is_not_silently_hidden(client):
    directory = history.history_directory()
    directory.mkdir(parents=True)
    (directory / "broken.json").write_text("{", encoding="utf-8")
    assert client.get("/api/history").status_code == 503
