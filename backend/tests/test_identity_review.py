from pathlib import Path

from app.agent import nodes
from tests.test_agent_full_graph import FakeVectorStore


def test_case08_identity_warning_has_both_sources_without_balance_error():
    root = Path(__file__).resolve().parents[2] / 'data/ordered_tests_v1/08_identity_mismatch/upload'
    state = {'application_id': 'identity-review', 'pdf_paths': [str(path) for path in sorted(root.glob('*.pdf'))], 'trace': [], 'errors': []}
    state.update(nodes.parse_node(state))
    state.update(nodes.extract_node(state, store=FakeVectorStore()))
    state.update(nodes.validate_node(state))
    state.update(nodes.ratios_node(state))
    findings = {item['code']: item for item in state['inconsistencies']}
    assert 'BALANCE_ARITHMETIC' not in findings
    mismatch = findings['HOLDER_SSM_MISMATCH']
    assert mismatch['severity'] == 'critical'
    assert 'ORCHID TEST SERVICES SDN BHD' in mismatch['message']
    assert 'LOTUS TEST TRADING SDN BHD' in mismatch['message']
    assert len(mismatch['citations']) == 2
    kinds = {state['document_kinds'][state['citation_sources'][chunk]['document_id']].value for chunk in mismatch['citations']}
    assert kinds == {'bank_statement', 'ssm_registration'}
    assert state['ratios']['bank_statement_metrics'][0]['net_change'] == '4000.00'
