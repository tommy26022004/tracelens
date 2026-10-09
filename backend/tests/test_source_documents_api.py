from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.api import applications
from app.core.config import settings
from app.ingestion.source_documents import SourceDocuments
from app.ingestion.store import RetrievalHit
from app.ingestion.synthetic import GeneratorConfig, generate
from app.main import app
from tests.test_agent_full_graph import FakeLLM, FakeVectorStore, _compile


@pytest.mark.parametrize("endpoint", ["/analyse", "/analyse/jobs"])
def test_uploaded_sources_survive_cleanup_and_open_correct_pdf(tmp_path, monkeypatch, endpoint):
    monkeypatch.setattr(settings, "source_documents_dir", tmp_path / "archive")
    vector_store = FakeVectorStore()
    monkeypatch.setattr(applications, "compile_graph", lambda: _compile(vector_store, FakeLLM()))

    class LookupStore:
        def get_chunk(self, chunk_id):
            chunk = next(
                (item for item in vector_store.upserted if item.chunk_id == chunk_id), None
            )
            if chunk is None:
                return None
            return RetrievalHit(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                kind=chunk.kind,
                text=chunk.text,
                page=chunk.page,
                score=1.0,
                source_metadata=chunk.source_metadata,
            )

    monkeypatch.setattr(applications, "VectorStore", LookupStore)
    pdf_one, _ = generate(GeneratorConfig(seed=42, n_transactions=6), tmp_path / "one")
    pdf_two, _ = generate(GeneratorConfig(seed=43, n_transactions=6), tmp_path / "two")
    payloads = [pdf_one.read_bytes(), pdf_two.read_bytes()]
    client = TestClient(app)
    response = client.post(
        "/api/applications" + endpoint,
        files=[("files", ("bank # A.pdf", payload, "application/pdf")) for payload in payloads],
    )
    assert response.status_code == 200
    if endpoint.endswith("jobs"):
        job_id = response.json()["job_id"]
        result = client.get(f"/api/applications/analyse/jobs/{job_id}").json()["result"]
    else:
        result = response.json()
    assert len(result["document_ids"]) == 2
    for document_id, original in zip(result["document_ids"], payloads, strict=True):
        encoded = quote(document_id, safe="/")
        pdf_response = client.get(f"/api/applications/source-pdfs/{encoded}")
        assert pdf_response.status_code == 200
        assert pdf_response.content == original
        source = SourceDocuments().lookup(document_id)
        assert source is not None and source[1] == "bank # A.pdf"
        detail = client.get(f"/api/applications/chunks/{encoded}/summary/0").json()
        assert detail["filename"] == "bank # A.pdf"
        assert detail["pdf_url"]
        assert detail["source_pages"]
        preview = client.get(detail["preview_url"] + "/" + str(detail["source_pages"][-1]))
        assert preview.status_code == 200
        assert preview.content.startswith(b"\x89PNG")
        assert client.get(detail["preview_url"] + "/9999").status_code == 404
    references = list(result["citation_sources"].values())
    assert references
    assert all(reference["filename"] == "bank # A.pdf" for reference in references)
    assert all(reference["pages"] for reference in references)
    assert client.get("/api/applications/source-pdfs/unknown").status_code == 404


def test_archive_lookup_cannot_resolve_arbitrary_files(tmp_path):
    source = SourceDocuments(tmp_path)
    outside = tmp_path.parent / "private.pdf"
    outside.write_bytes(b"private")
    assert source.lookup("../private") is None
