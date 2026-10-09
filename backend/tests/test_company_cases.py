import pytest
from fastapi.testclient import TestClient

from app.api.history import save_record
from app.core.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "source_documents_dir", tmp_path / "sources")
    return TestClient(app)


def test_cases_start_empty_and_default_to_test(client):
    save_record({"category": "analysis", "application_id": "old", "result": {"application_id": "old"}})
    assert client.get('/api/cases').json() == {"items": []}
    record = client.post('/api/cases', json={"company": "Lotus"}).json()
    assert record['environment'] == 'test'
    assert record['runs'] == []
    assert client.post('/api/cases', json={"company": "   "}).status_code == 422


def test_link_run_and_append_review_without_changing_snapshot(client):
    case = client.post('/api/cases', json={"company": "Lotus", "reference": "TEST-001"}).json()
    run = save_record({"category": "analysis", "application_id": "test-run", "document_count": 1, "result": {"application_id": "test-run"}})
    endpoint = f"/api/cases/{case['id']}/updates"
    response = client.post(endpoint, json={"status": "awaiting_documents", "note": "Need audited reports", "run_id": run['id']})
    assert response.status_code == 200
    assert response.json()['runs'][0]['id'] == run['id']
    assert client.post(endpoint, json={"status": "reviewed", "note": "Reviewed, not approved"}).status_code == 200
    stored = client.get('/api/cases').json()['items'][0]
    assert len(stored['events']) == 2
    assert stored['events'][0]['note'] == 'Need audited reports'
    assert client.get(f"/api/history/{run['id']}").json() == run
    assert client.post(endpoint, json={"status": "reviewed", "run_id": run['id']}).status_code == 409
    assert client.post(endpoint, json={"status": "approved"}).status_code == 422


def test_reject_non_analysis_and_unknown_case(client):
    case = client.post('/api/cases', json={"company": "Lotus"}).json()
    note = save_record({"category": "note", "title": "Not a run"})
    assert client.post(f"/api/cases/{case['id']}/updates", json={"status": "under_review", "run_id": note['id']}).status_code == 422
    assert client.post('/api/cases/00000000-0000-0000-0000-000000000000/updates', json={"status": "under_review"}).status_code == 404
