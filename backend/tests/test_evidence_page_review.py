from pathlib import Path

from app.agent import nodes
from tests.test_agent_full_graph import FakeLLM, FakeVectorStore


def test_case11_high_concentration_uses_page_three_and_cannot_be_adequate():
    root = Path(__file__).resolve().parents[2] / "data/ordered_tests_v1/11_evidence_page_3"
    store = FakeVectorStore()
    state = {
        "application_id": "evidence-page-three-review",
        "pdf_paths": [str(path) for path in sorted((root / "upload").glob("*.pdf"))],
        "trace": [],
        "errors": [],
    }

    state.update(nodes.parse_node(state))
    state.update(nodes.extract_node(state, store=store))
    state.update(nodes.validate_node(state))
    state.update(nodes.ratios_node(state))
    state.update(nodes.assess_5c_node(state, llm=FakeLLM(), store=store))

    conditions = state["five_c"]["conditions"]
    assert conditions["rating"] == "weak"
    assert "65%" in conditions["reasoning"]
    assert "70%" in conditions["reasoning"]
    assert conditions["evidence_chunk_ids"]
    for chunk_id in conditions["evidence_chunk_ids"]:
        source = state["citation_sources"][chunk_id]
        assert source["filename"] == "management.pdf"
        assert source["pages"] == [3]

    conditions_query = next(
        query for query in state["retrieval"]["queries"] if query["topic"] == "conditions"
    )
    assert conditions_query["status"] == "retrieved"
    assert set(conditions["evidence_chunk_ids"]).issubset(conditions_query["selected_chunk_ids"])
