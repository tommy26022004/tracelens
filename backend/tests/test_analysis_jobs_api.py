"""HTTP end-to-end tests for large-package analysis jobs."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import applications
from app.main import app

client = TestClient(app)


def test_job_upload_preserves_duplicate_filenames(monkeypatch) -> None:
    captured_paths: list[str] = []

    def fake_execute(application_id: str, pdf_paths: list[str]) -> applications.AnalysisResponse:
        captured_paths.extend(pdf_paths)
        return applications.AnalysisResponse(
            application_id=application_id,
            document_ids=[Path(path).stem for path in pdf_paths],
            document_kinds={},
        )

    monkeypatch.setattr(applications, "_execute_analysis", fake_execute)
    response = client.post(
        "/api/applications/analyse/jobs",
        files=[
            ("files", ("statement.pdf", b"%PDF-1.4 first", "application/pdf")),
            ("files", ("statement.pdf", b"%PDF-1.4 second", "application/pdf")),
        ],
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/applications/analyse/jobs/{job_id}")

    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert status.json()["progress"] == 100
    assert len(captured_paths) == 2
    assert Path(captured_paths[0]).name == "001_statement.pdf"
    assert Path(captured_paths[1]).name == "002_statement.pdf"


def test_job_rejects_more_than_fifty_files() -> None:
    response = client.post(
        "/api/applications/analyse/jobs",
        files=[
            ("files", (f"document_{index}.pdf", b"%PDF", "application/pdf")) for index in range(51)
        ],
    )
    assert response.status_code == 400
    assert "at most 50 PDFs" in response.text


def test_stream_updates_each_completed_stage(monkeypatch):
    job_id = "progress-stages"
    applications._jobs[job_id] = applications.AnalysisJobResponse(
        job_id=job_id, status=applications.JobStatus.PROCESSING, progress=10, phase="reading")
    observed = []

    class StreamingGraph:
        def stream(self, initial, *, config, stream_mode):
            assert stream_mode == "values"
            for node in ["parse", "extract", "validate", "ratios", "assess_5c", "summarise"]:
                yield {"trace": [SimpleNamespace(node=node)]}
                observed.append(applications._jobs[job_id].progress)
            yield {"trace": []}

    monkeypatch.setattr(applications, "compile_graph", lambda: StreamingGraph())
    try:
        applications._execute_analysis_graph(job_id, [])
        assert observed == [20, 40, 50, 55, 80, 95]
        assert applications._jobs[job_id].phase == "saving"
    finally:
        applications._jobs.pop(job_id, None)


def test_failed_job_does_not_show_one_hundred_percent(monkeypatch, tmp_path):
    def fail(application_id, paths):
        applications._update_job_progress(application_id, 55, "assessing")
        raise RuntimeError("Test failure")

    monkeypatch.setattr(applications, "_execute_analysis", fail)
    job_id = "failed-progress"
    try:
        applications._run_analysis_job(job_id, tmp_path / "upload", [])
        assert applications._jobs[job_id].status == applications.JobStatus.FAILED
        assert applications._jobs[job_id].progress == 55
    finally:
        applications._jobs.pop(job_id, None)
