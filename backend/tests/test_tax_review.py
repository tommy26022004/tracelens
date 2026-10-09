import json
from pathlib import Path

from app.agent import nodes
from app.agent.retrieval import context_citations, retrieve_evidence, tax_evidence
from tests.test_agent_full_graph import FakeVectorStore


def test_case05_tax_fields_prompt_and_citation_context():
    root = Path(__file__).resolve().parents[2] / "data/ordered_tests_v1/05_tax_extraction"
    state = {
        "application_id": "tax-review",
        "pdf_paths": [str(root / "upload/tax.pdf")],
        "trace": [],
        "errors": [],
    }
    state.update(nodes.parse_node(state))
    state.update(nodes.extract_node(state, store=FakeVectorStore()))
    state.update(nodes.validate_node(state))
    state.update(nodes.ratios_node(state))
    tax = state["tax_returns"][0]
    truth = json.loads((root / "ground_truth.json").read_text(encoding="utf-8"))["documents"][
        "tax.pdf"
    ]
    for name, expected in truth["fields"].items():
        assert str(getattr(tax, name)) == str(expected)
        assert tax.source_fields[name].page == truth["field_pages"][name]
    evidence = tax_evidence(state)
    assert evidence[0]["gross_business_income"] == "120000.00"
    prompt = nodes._package_evidence(state)
    assert "5400.00" in prompt
    assert "proof of payment" in prompt
    package_payload = json.loads(prompt)
    assert "documents" not in package_payload["package_inventory"]
    assert "sha256" not in prompt
    bundle = retrieve_evidence(state, FakeVectorStore())
    assert any(query.topic == "tax" and query.status != "not_available" for query in bundle.queries)
    assert evidence[0]["chunk_id"] in context_citations(state, bundle)
