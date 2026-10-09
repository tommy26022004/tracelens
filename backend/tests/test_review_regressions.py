import json
from datetime import date
from decimal import Decimal

import pytest

from app.agent import nodes
from app.agent.retrieval import retrieve_evidence
from app.explainability.summary import RiskSummary, has_unsupported_critical_label
from app.validation.checks import Inconsistency, Severity
from app.ingestion.extractor import extract_bank_statement
from app.ingestion.parser import parse_pdf
from app.ratios.bank_statement_metrics import compute_metrics
from scripts.generate_ordered_test_pack import bank
from tests.test_agent_full_graph import FakeLLM, FakeVectorStore
from tests.test_assessment_evidence import _validated_state
from tests.test_retrieval import FixedStore, _chunk, _state


def test_authored_bank_all_fields_and_transactions(tmp_path):
    path = tmp_path / "bank.pdf"
    truth = bank(path)
    actual = extract_bank_statement(parse_pdf(path))
    payload = actual.model_dump(mode="json")
    for field, expected in truth["fields"].items():
        assert payload[field] == expected, field
    assert len(payload["transactions"]) == len(truth["transactions"])
    for actual_row, expected_row in zip(payload["transactions"], truth["transactions"], strict=True):
        for field, expected in expected_row.items():
            assert actual_row[field] == expected, field
    metrics = compute_metrics(actual, "test/bank")
    assert metrics.period_days == 31
    assert metrics.avg_daily_inflow == Decimal("322.58")
    assert metrics.avg_daily_outflow == Decimal("193.55")


@pytest.mark.parametrize("start,end,days", [
    (date(2025, 1, 1), date(2025, 1, 1), 1),
    (date(2025, 2, 1), date(2025, 2, 28), 28),
    (date(2024, 2, 1), date(2024, 2, 29), 29),
    (date(2025, 4, 1), date(2025, 4, 30), 30),
])
def test_inclusive_days(tmp_path, start, end, days):
    path = tmp_path / "bank.pdf"
    bank(path)
    statement = extract_bank_statement(parse_pdf(path))
    statement.statement_period_start = start
    statement.statement_period_end = end
    assert compute_metrics(statement, "test").period_days == days


def test_reversed_period_rejected(tmp_path):
    path = tmp_path / "bank.pdf"
    bank(path)
    statement = extract_bank_statement(parse_pdf(path))
    statement.statement_period_start = date(2025, 2, 1)
    with pytest.raises(ValueError, match="precedes"):
        compute_metrics(statement, "test")


def test_bank_only_capacity_guard_reaches_summary(tmp_path):
    state = _validated_state(tmp_path)
    provider = FakeLLM()
    state.update(nodes.assess_5c_node(state, llm=provider, store=FakeVectorStore()))
    assert state["five_c"]["capacity"]["rating"] == "insufficient_data"
    state.update(nodes.summarise_node(state, llm=provider))
    assert "Capacity: insufficient_data" in provider.calls[-1][0]
    assert json.loads(state["risk_summary"])["body"]


def test_inventory_absence_is_not_vector_query():
    state = _state(_chunk())
    state["inconsistencies"] = [
        {"code": "MISSING_BANK_MONTHS", "message": "Missing months", "citations": []},
        {"code": "MISSING_CORE_DOCUMENTS", "message": "Missing documents", "citations": []},
    ]
    store = FixedStore([])
    result = retrieve_evidence(state, store)
    assert all(not record.topic.startswith("validation:") for record in result.queries)
    assert all("Missing" not in query for query, _ in store.calls)


@pytest.mark.parametrize("text", ["A critical warning was raised.", "The severity: critical", "A critical validation finding."])
def test_rejects_unsupported_critical_severity(text):
    summary = RiskSummary(headline="Review", body=text)
    warning = Inconsistency(code="MISSING_CORE_DOCUMENTS", severity=Severity.WARNING, message="Missing documents")
    assert has_unsupported_critical_label(summary, [warning])
    warning.severity = Severity.CRITICAL
    assert not has_unsupported_critical_label(summary, [warning])


def test_severity_guard_does_not_rewrite_ordinary_language():
    summary = RiskSummary(headline="Review", body="Financial statements are critical to the review.")
    assert not has_unsupported_critical_label(summary, [])


def test_summary_severity_mismatch_uses_logged_fallback(tmp_path):
    state = _validated_state(tmp_path)
    state.update(nodes.assess_5c_node(state, llm=FakeLLM(), store=FakeVectorStore()))
    for finding in state["inconsistencies"]:
        finding["severity"] = "warning"

    class IncorrectSeverityLLM(FakeLLM):
        def generate_structured(self, prompt, schema):
            return RiskSummary(headline="Review", body="The system identified a critical warning about missing documents.")

    output = nodes.summarise_node(state, llm=IncorrectSeverityLLM())
    assert "critical warning" not in json.loads(output["risk_summary"])["body"]
    assert any("Unsupported critical severity" in error.message for error in output["errors"])
