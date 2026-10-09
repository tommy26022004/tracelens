import json
from pathlib import Path

import pytest

from app.agent import nodes
from app.ingestion.synthetic import GeneratorConfig, generate
from tests.test_agent_full_graph import FakeLLM, FakeVectorStore, UnavailableLLM


def _validated_state(tmp_path: Path) -> dict:
    pdf, _ = generate(GeneratorConfig(seed=42, n_transactions=6), tmp_path)
    state = {"application_id": "evidence-test", "pdf_paths": [str(pdf), str(pdf)]}
    state.update(nodes.parse_node(state))
    state.update(nodes.extract_node(state, store=FakeVectorStore()))
    state.update(nodes.validate_node(state))
    state.update(nodes.ratios_node(state))
    return state


def test_final_nodes_consume_canonical_results_without_recomputation(tmp_path, monkeypatch):
    state = _validated_state(tmp_path)
    state["ratios"]["bank_statement_metrics"][0]["net_change"] = "12345.67"
    state["ratios"]["package_cash_flow"]["net_cash_change"] = "76543.21"

    def unexpected_recomputation(*args, **kwargs):
        raise AssertionError("Final nodes must consume the validated state")

    for name in (
        "run_checks",
        "run_cross_doc_checks",
        "compute_metrics",
        "compute_financial_ratios",
    ):
        monkeypatch.setattr(nodes, name, unexpected_recomputation)
    provider = FakeLLM()
    state.update(nodes.assess_5c_node(state, llm=provider, store=FakeVectorStore()))
    state.update(nodes.summarise_node(state, llm=provider))
    for prompt, _ in provider.calls:
        assert "DUPLICATE_DOCUMENT" in prompt
        assert "MISSING_BANK_MONTHS" in prompt
        assert "12345.67" in prompt
        assert "76543.21" in prompt
        assert state["statements"][0].bank_name in prompt
    summary = json.loads(state["risk_summary"])
    assert "DUPLICATE_DOCUMENT" in summary["body"]
    assert "MISSING_BANK_MONTHS" in summary["body"]
    assert any(
        "DUPLICATE_DOCUMENT" in flag
        for flag in state["five_c"]["character"]["flags_for_human_review"]
    )


def test_fallback_preserves_uncited_inventory_findings_and_deduplicated_totals(tmp_path):
    state = _validated_state(tmp_path)
    expected_net = state["ratios"]["package_cash_flow"]["net_cash_change"]
    state.update(nodes.assess_5c_node(state, llm=UnavailableLLM(), store=FakeVectorStore()))
    state.update(nodes.summarise_node(state, llm=UnavailableLLM()))
    summary = json.loads(state["risk_summary"])
    assert "DUPLICATE_DOCUMENT" in summary["body"]
    assert "MISSING_BANK_MONTHS" in summary["body"]
    assert "(package inventory check)" in summary["body"]
    assert f"{float(expected_net):,.2f}" in summary["body"]
    assert "No deterministic cross-document inconsistency" not in summary["body"]


def test_assessment_requires_prior_node_outputs():
    with pytest.raises(ValueError, match="validation and ratios"):
        nodes.assess_5c_node({}, llm=FakeLLM())
