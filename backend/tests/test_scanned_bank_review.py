import json
from pathlib import Path

from app.agent import nodes
from tests.test_agent_full_graph import FakeVectorStore, UnavailableLLM


def test_scanned_bank_requires_ocr_without_claiming_successful_extraction():
    root = Path(__file__).resolve().parents[2] / "data/ordered_tests_v1/12_scanned_bank"
    store = FakeVectorStore()
    state = {
        "application_id": "scanned-bank-review",
        "pdf_paths": [str(path) for path in sorted((root / "upload").glob("*.pdf"))],
        "trace": [],
        "errors": [],
    }

    state.update(nodes.parse_node(state))
    extraction = nodes.extract_node(state, store=store)
    state.update(extraction)
    state.update(nodes.validate_node(state))
    state.update(nodes.ratios_node(state))
    state.update(nodes.assess_5c_node(state, llm=UnavailableLLM(), store=store))
    state.update(nodes.summarise_node(state, llm=UnavailableLLM()))

    document_id = state["document_ids"][0]
    inventory = state["package_inventory"]
    assert state["needs_ocr_pages"][document_id] == [1]
    assert inventory["extracted_documents"] == 0
    assert inventory["failed_documents"] == 1
    assert inventory["documents"][0]["extraction_status"] == "ocr_required"
    assert any(
        "OCR is required but is not currently supported" in error.message
        for error in extraction["errors"]
        if error.node == "extract"
    )

    assert all(dimension["rating"] == "insufficient_data" for dimension in state["five_c"].values())
    assert state.get("chunks", []) == []

    summary = json.loads(state["risk_summary"])
    assert "Image-only PDF detected" in summary["headline"]
    assert "No uploaded document was successfully extracted" in summary["body"]
    assert summary["cited_chunk_ids"] == []

    finding_codes = {finding["code"] for finding in state["inconsistencies"]}
    checks = summary["recommended_human_checks"]
    assert all(
        not any(check.lower().startswith(f"{code.lower()}:") for code in finding_codes)
        for check in checks
    )
    assert (
        sum(
            "bank statement" in check.lower() or "banking history" in check.lower()
            for check in checks
        )
        <= 1
    )
    assert sum("audited financial" in check.lower() for check in checks) <= 1
