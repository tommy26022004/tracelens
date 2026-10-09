import json
from pathlib import Path

from app.agent import nodes
from tests.test_agent_full_graph import FakeVectorStore, UnavailableLLM


def test_case09_fallback_explains_revenue_mismatch_conservatively():
    root = Path(__file__).resolve().parents[2] / "data/ordered_tests_v1/09_revenue_mismatch"
    store = FakeVectorStore()
    state = {
        "application_id": "revenue-mismatch-review",
        "pdf_paths": [str(path) for path in sorted((root / "upload").glob("*.pdf"))],
        "trace": [],
        "errors": [],
    }

    state.update(nodes.parse_node(state))
    state.update(nodes.extract_node(state, store=store))
    state.update(nodes.validate_node(state))
    state.update(nodes.ratios_node(state))
    state.update(nodes.assess_5c_node(state, llm=UnavailableLLM(), store=store))
    state.update(nodes.summarise_node(state, llm=UnavailableLLM()))

    revenue_finding = next(
        item for item in state["inconsistencies"] if item["code"] == "AUDITED_VS_TAX_REVENUE"
    )
    assert revenue_finding["severity"] == "warning"
    assert len(revenue_finding["citations"]) == 2
    assert state["five_c"]["conditions"]["rating"] == "insufficient_data"
    assert "external market" in state["five_c"]["conditions"]["reasoning"]
    assert "No bank-activity evidence" in state["five_c"]["character"]["reasoning"]
    assert "Limited bank activity" not in state["five_c"]["character"]["reasoning"]

    summary = json.loads(state["risk_summary"])
    narrative = f"{summary['headline']} {summary['body']}"
    assert "Audited revenue RM 120000.00" in narrative
    assert "tax-declared gross income RM 60000.00" in narrative
    assert "deterministic fallback" in narrative
    assert all(citation in summary["cited_chunk_ids"] for citation in revenue_finding["citations"])
    assert "tax evasion" not in narrative.lower()
    assert "fraud" not in narrative.lower()
