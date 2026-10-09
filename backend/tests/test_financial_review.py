import json
from pathlib import Path

from app.agent import nodes
from app.ingestion.financials_extractor import extract_audited_financials
from app.ingestion.parser import parse_pdf
from app.ratios.financial_ratios import compute_financial_ratios
from app.ratios.package_metrics import compute_financial_trend
from tests.test_agent_full_graph import FakeLLM, FakeVectorStore


def fixture_path():
    return Path(__file__).resolve().parents[2] / 'data/ordered_tests_v1/04_financials_and_ratios'


def test_case04_fields_ratios_and_both_years():
    root = fixture_path()
    financials = extract_audited_financials(parse_pdf(root / 'upload/financials.pdf'))
    truth = json.loads((root / 'ground_truth.json').read_text(encoding='utf-8'))['documents']['financials.pdf']
    for period in financials.periods:
        for name, value in truth['periods'][str(period.period_end.year)].items():
            assert str(getattr(period, name)) == value
            assert period.source_fields[name].page == truth['field_pages'][name]
    ratios = compute_financial_ratios(financials, 'fin')
    assert str(ratios.current_ratio.value) == '2.0000'
    assert str(ratios.net_profit_margin.value) == '0.1800'
    assert str(ratios.interest_coverage.value) == '10.0000'
    assert str(ratios.debt_to_equity.value) == '1.0000'
    assert ratios.dsr.value is None
    assert ratios.dsr.band.value == 'insufficient_data'
    assert str(ratios.inputs['cash_from_operations']) == '28000.00'
    trend = compute_financial_trend([financials])
    assert trend.years == [2024, 2025]
    assert trend.revenue_growth_rates[2025] == 20


def test_financial_only_capacity_has_partial_evidence_not_strength():
    state = {'application_id': 'financial-review', 'pdf_paths': [str(fixture_path() / 'upload/financials.pdf')], 'trace': [], 'errors': []}
    state.update(nodes.parse_node(state))
    state.update(nodes.extract_node(state, store=FakeVectorStore()))
    state.update(nodes.validate_node(state))
    state.update(nodes.ratios_node(state))
    state.update(nodes.assess_5c_node(state, llm=FakeLLM(), store=FakeVectorStore()))
    capacity = state['five_c']['capacity']
    assert capacity['rating'] == 'insufficient_data'
    assert '28000.00' in capacity['reasoning']
    assert capacity['evidence_chunk_ids']
    query = next(query for query in state['retrieval']['queries'] if query['topic'] == 'capacity')
    assert query['selected_chunk_ids']
    assert not any('No relevant excerpts retrieved for capacity' in warning for warning in state['retrieval']['warnings'])
