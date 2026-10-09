from pathlib import Path

from app.agent import nodes
from tests.test_agent_full_graph import FakeLLM, FakeVectorStore


def test_clean_package_does_not_establish_strong_character():
    root = Path(__file__).resolve().parents[2] / 'data/ordered_tests_v1/06_clean_package/upload'
    state = {'application_id': 'clean-review', 'pdf_paths': [str(path) for path in sorted(root.glob('*.pdf'))], 'trace': [], 'errors': []}
    state.update(nodes.parse_node(state))
    state.update(nodes.extract_node(state, store=FakeVectorStore()))
    state.update(nodes.validate_node(state))
    state.update(nodes.ratios_node(state))
    state.update(nodes.assess_5c_node(state, llm=FakeLLM(), store=FakeVectorStore()))
    assert state['package_inventory']['total_documents'] == 4
    assert state['package_inventory']['total_pages'] == 5
    assert state['package_inventory']['missing_core_kinds'] == []
    assert {item['code'] for item in state['inconsistencies']} == {'MISSING_BANK_MONTHS'}
    assert state['five_c']['character']['rating'] == 'insufficient_data'
    assert 'do not verify' in state['five_c']['character']['reasoning']
    assert state['five_c']['character']['flags_for_human_review']
