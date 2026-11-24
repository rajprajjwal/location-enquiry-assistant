"""Customer context must remain attached when quantities cross component boundaries."""
import pytest

from copilot.diagnostics.extraction import extract_supplied_facts
from copilot.diagnostics.facts import DiagnosticFact, build_diagnostic_state
from copilot.qualification.contract import QualificationPlan
from copilot.qualification.facts import context_from_result, merge_model_facts


def context(enquiry, state=None, volume=None):
    state = state or build_diagnostic_state(enquiry)
    result = {'diagnostic_context': {'interpretation': {'api': 'directions', 'intent': 'pricing_quote'}},
              'outputs': {'qualification_details': {'monthly_volume': volume}}}
    return context_from_result(result, state, enquiry), state


@pytest.mark.parametrize('query', [
    'The docs include 20,000 requests per month for free.',
    'The API supports 20,000 requests per month.',
    'Do we send 20,000 requests per month?',
    'If we send 20,000 requests per month, what would it cost?',
])
def test_stripped_quote_cannot_promote_a_limit_question_or_assumption(query):
    from copilot.enquiry_interpretation.postcheck import postcheck
    from tests.support.helpers import model_json
    enquiry = {'query': query}
    volume = {'raw': '20,000 requests per month', 'requests_per_month': 20000, 'unit': 'requests_per_month'}
    state = build_diagnostic_state(enquiry)
    state.facts['monthly_volume'] = DiagnosticFact(field='monthly_volume', value=volume,
                                                   source='query', evidence=volume['raw'])
    actual, _ = context(enquiry, state, volume)
    assert actual.facts['monthly_volume'].status == 'missing'
    plan = QualificationPlan.model_validate({'reason': 'Test quote binding.', 'supplied_facts': [
        {'field': 'monthly_volume', 'value': 20000, 'evidence': volume['raw']},
    ]})
    merge_model_facts(state, plan, enquiry)
    assert state.facts['monthly_volume'].status == 'missing'
    assert not {'workload', 'workload_period'} & {item['field'] for item in extract_supplied_facts(enquiry)}
    output = postcheck(model_json(qualification={
        'monthly_volume': {'value': volume['raw'], 'evidence': volume['raw']},
    }), query=query)['output']
    assert output['qualification_details']['monthly_volume'] is None


def test_actual_workload_and_estimate_scenario_stay_separate():
    enquiry = {'query': 'Assume 50,000 requests per month for an estimate.',
               'history': [{'role': 'user', 'text': 'We send 20,000 requests per month.'}]}
    actual, state = context(enquiry)
    assert actual.facts['monthly_volume'].value['requests_per_month'] == 20000
    assert state.facts['monthly_volume_assumption'].value['requests_per_month'] == 50000
    assert state.facts['monthly_volume_assumption'].value['basis'] == 'scenario_assumption'


def test_older_model_workload_cannot_override_new_customer_correction():
    enquiry = {'query': 'Actually we send 60,000 requests per month.',
               'history': [{'role': 'user', 'text': 'We send 20,000 requests per month.'}]}
    actual, state = context(enquiry)
    plan = QualificationPlan.model_validate({'reason': 'Test history precedence.', 'supplied_facts': [
        {'field': 'monthly_volume', 'value': 20000, 'evidence': '20,000 requests per month'},
    ]})
    merge_model_facts(state, plan, enquiry)
    assert state.facts['monthly_volume'].value['requests_per_month'] == 60000


def test_trusted_external_typed_workload_keeps_its_source():
    enquiry = {'query': 'Please compare the options.'}
    state = build_diagnostic_state(enquiry)
    value = {'raw': '20k', 'requests_per_month': 20000, 'unit': 'requests_per_month'}
    state.facts['monthly_volume'] = DiagnosticFact(field='monthly_volume', value=value, source='state_store')
    actual, _ = context(enquiry, state)
    assert actual.facts['monthly_volume'].status == 'supplied'
    assert actual.facts['monthly_volume'].source == 'state_store'


@pytest.mark.parametrize(('query', 'count'), [
    ('What will 50,000 Google two-wheeler routes a month cost us in India?', 50000),
    ('Compare two providers for 6,000,000 traffic-aware route requests a month.', 6000000),
    ('Google vs Mapbox reverse geocoding for 4,000,000 lookups a month (display only)?', 4000000),
    ('Free reverse geocoding options for a hobby app with 20,000 lookups a month?', 20000),
    ('Compare cost, limits, and coverage for Google Maps and Mapbox at 150,000 requests per month without traffic.', 150000),
])
def test_scenario_inputs_remain_available_without_becoming_confirmed_usage(query, count):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from copy import deepcopy
    from copilot.qualification.planning import plan_qualification

    enquiry = {'query': query}
    actual, state = context(enquiry)
    assert 'monthly_volume' not in actual.facts
    assert actual.assumptions['monthly_volume'].value['requests_per_month'] == count
    client = Mock()
    client.complete.return_value = SimpleNamespace(finish_reason='stop', text='{"supplied_facts": [], "groups": [], "reason": "Use the stated scenario."}')
    result = {'status': 'final', 'pending_reply': None, 'clarifying_questions': {'needed': False, 'questions': []},
              'outputs': {'qualification_details': {}, 'responsible_role': {'owner': 'Sales'},
                          'next_action': {'action_type': 'answer_directly'}, 'proposed_record_update': {'applicable': False}},
              'diagnostic_context': {'state': state.model_dump(), 'retrieved_evidence': [],
                                     'interpretation': {'api': 'directions', 'intent': 'pricing_quote'}}}
    before = deepcopy(result)
    after = plan_qualification(result, enquiry, client=client)
    assert not any('monthly_volume' in group['fields'] for group in after['follow_up_selection'].get('groups', []))
    for field in ('status', 'pending_reply', 'clarifying_questions'):
        assert after[field] == before[field]
    for field in ('responsible_role', 'next_action', 'proposed_record_update'):
        assert after['outputs'][field] == before['outputs'][field]
