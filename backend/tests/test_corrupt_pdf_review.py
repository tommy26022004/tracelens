import json
from pathlib import Path

from app.agent import nodes
from tests.test_agent_full_graph import FakeVectorStore, UnavailableLLM


class UnexpectedLLM(UnavailableLLM):
    def __init__(self):
        self.calls = 0

    def generate_structured(self, prompt, schema):
        self.calls += 1
        return super().generate_structured(prompt, schema)


def test_corrupt_pdf_becomes_explicit_processing_failure_without_financial_claims():
    root = Path(__file__).resolve().parents[2] / "data/ordered_tests_v1/13_corrupt_pdf"
    store = FakeVectorStore()
    provider = UnexpectedLLM()
    state = {
        "application_id": "corrupt-pdf-review",
        "pdf_paths": [str(path) for path in sorted((root / "upload").glob("*.pdf"))],
        "trace": [],
        "errors": [],
    }

    parsing = nodes.parse_node(state)
    state.update(parsing)
    state.update(nodes.extract_node(state, store=store))
    state.update(nodes.validate_node(state))
    state.update(nodes.ratios_node(state))
    state.update(nodes.assess_5c_node(state, llm=provider, store=store))
    state.update(nodes.summarise_node(state, llm=provider))

    document_id = state["document_ids"][0]
    parse_error = parsing["errors"][0]
    assert parsing["trace"][0].summary.startswith("Parsed 0/1 PDFs")
    assert provider.calls == 0
    assert state["document_parse_failures"][document_id] == parse_error.message
    assert "could not be opened as a valid PDF" in parse_error.message
    assert "/tmp/" not in parse_error.message
    assert "fyp_job_" not in parse_error.message

    inventory = state["package_inventory"]
    assert inventory["total_documents"] == 1
    assert inventory["extracted_documents"] == 0
    assert inventory["failed_documents"] == 1
    assert inventory["documents"][0]["extraction_status"] == "parse_failed"
    assert state.get("chunks", []) == []
    assert all(dimension["rating"] == "insufficient_data" for dimension in state["five_c"].values())

    summary = json.loads(state["risk_summary"])
    assert "Invalid or damaged PDF detected" in summary["headline"]
    assert "no financial conclusion is supported" in summary["headline"]
    assert summary["cited_chunk_ids"] == []
