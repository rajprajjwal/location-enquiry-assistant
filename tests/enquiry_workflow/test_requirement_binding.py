"""Verify literal supplied facts, ambiguity handling and repeated-question suppression."""
from copy import deepcopy
import json

import pytest

from copilot.diagnostics.facts import DiagnosticFact, build_diagnostic_state
from copilot.qualification.contract import QualificationPlan
from copilot.qualification.extraction import extract_requirements
from copilot.qualification.facts import context_from_result, merge_model_facts
from copilot.qualification.planning import plan_qualification
from tests.enquiry_workflow.test_qualification import client_for, result_for


@pytest.mark.parametrize('query,field,value', [
    ('They only want rooftop precision.', 'rooftop_hard_filter', True),
    ('The prospect only accepts results at rooftop precision.', 'rooftop_hard_filter', True),
    ('We need structured address components.', 'address_elements_required', True),
    ('They require an address broken into elements.', 'address_elements_required', True),
    ('We do not need address components.', 'address_elements_required', False),
    ('We do not require rooftop-only results.', 'rooftop_hard_filter', False),
    ('We must store addresses.', 'storage_required', True),
    ('We do not store addresses.', 'storage_required', False),
    ('We need live traffic.', 'traffic_required', True),
    ("We don't need live traffic.", 'traffic_required', False),
    ('Each route visits 12 stops.', 'max_stops', '12'),
    ('Plan 15–20 outlets per route.', 'max_stops', '15–20'),
    ('Use a route with 18 waypoints.', 'max_stops', '18'),
    ('Compare with and without traffic.', 'traffic_scope', 'with_and_without'),
])
def test_explicit_requirement_keeps_value_and_exact_provenance(query, field, value):
    facts = {f['field']: f for f in extract_requirements({'query': query})}
    assert facts[field]['value'] == value
    fact = facts[field]
    assert query[fact['start']:fact['end']] == fact['evidence']


@pytest.mark.parametrize('query,field', [
    ('They may need address components.', 'address_elements_required'),
    ('Do they need address components?', 'address_elements_required'),
    ('What are address components?', 'address_elements_required'),
    ('We optionally filter to rooftop precision.', 'rooftop_hard_filter'),
    ('We need addresses with rooftop precision.', 'rooftop_hard_filter'),
    ("We don't only want rooftop precision.", 'rooftop_hard_filter'),
    ('We may store addresses.', 'storage_required'),
    ('Do we need to store addresses?', 'storage_required'),
    ('We do not need live traffic.', 'storage_required'),
    ('We have 20 outlets to visit daily.', 'max_stops'),
    ('Daily plans with 15–20 outlets.', 'max_stops'),
    ('Could each route have 20 stops?', 'max_stops'),
    ('We might need 20 stops per route.', 'max_stops'),
    ('Compare with and without traffic.', 'traffic_required'),
])
def test_ambiguous_or_unrelated_text_does_not_establish_requirement(query, field):
    assert field not in {f['field'] for f in extract_requirements({'query': query})}


def test_customer_history_is_reused_but_assistant_assertions_are_excluded():
    enquiry = {'query': 'Recommend a service.', 'history': [
        {'role': 'assistant', 'text': 'They only want rooftop precision.'},
        {'role': 'user', 'text': 'We need address components.'},
    ]}
    facts = {f['field']: f for f in extract_requirements(enquiry)}
    assert 'rooftop_hard_filter' not in facts
    assert facts['address_elements_required']['source'] == 'history[1]'


def test_empty_model_proposals_cannot_repeat_explicit_precision_or_components():
    enquiry = {'query': 'They only want results at rooftop precision, and they need an address broken into elements. What should we ask?'}
    original = result_for(enquiry)
    original['diagnostic_context']['interpretation']['api'] = 'reverse_geocode'
    before = deepcopy(original)
    updated = plan_qualification(original, enquiry, client=client_for([]))
    groups = updated['follow_up_selection']['groups']
    assert [g['fields'] for g in groups] == [['alternative_providers']]
    for field in ['status', 'pending_reply', 'clarifying_questions']:
        assert updated[field] == before[field]
    for field in ['next_action', 'responsible_role', 'proposed_record_update']:
        assert updated['outputs'][field] == before['outputs'][field]


def test_unbound_outlet_count_cannot_enter_through_model_or_stale_saved_fact():
    enquiry = {'query': 'Recommend routing for daily beat plans with 15–20 outlets.'}
    state = build_diagnostic_state(enquiry)
    state.facts['max_stops'] = DiagnosticFact(field='max_stops', value='15–20', source='query', evidence='15–20 outlets')
    context = context_from_result(result_for(enquiry), state, enquiry)
    assert context.facts['max_stops'].status == 'missing'
    plan = QualificationPlan.model_validate({'reason': 'Check route scope.', 'supplied_facts': [
        {'field': 'max_stops', 'value': '15–20', 'evidence': '15–20 outlets'}]})
    merge_model_facts(state, plan, enquiry)
    assert state.facts['max_stops'].status == 'missing'
    original = result_for(enquiry)
    updated = plan_qualification(original, enquiry, client=client_for([], plan.model_dump()['supplied_facts']))
    assert any('max_stops' in group['fields'] for group in updated['follow_up_selection']['groups'])


def test_model_route_size_requires_the_same_bound_numeric_value():
    enquiry = {'query': 'We need 12 stops per route.'}
    for value, expected in [(12, True), (20, False)]:
        state = build_diagnostic_state(enquiry)
        plan = QualificationPlan.model_validate({'reason': 'Check route scope.', 'supplied_facts': [
            {'field': 'max_stops', 'value': value, 'evidence': enquiry['query']}]})
        merge_model_facts(state, plan, enquiry)
        assert ('max_stops' in state.facts) is expected


def test_explicit_false_survives_a_contradictory_model_proposal():
    enquiry = {'query': 'We do not need address components.'}
    state = build_diagnostic_state(enquiry)
    context_from_result(result_for(enquiry), state, enquiry)
    plan = QualificationPlan.model_validate({'reason': 'Known requirement.', 'supplied_facts': [
        {'field': 'address_elements_required', 'value': True, 'evidence': enquiry['query']}]})
    merge_model_facts(state, plan, enquiry)
    assert state.facts['address_elements_required'].value is False


@pytest.mark.parametrize('query,expected', [
    ('We do not require live traffic, but we need address components.', {'traffic_required': False, 'address_elements_required': True}),
    ('We only want rooftop precision, not address components.', {'rooftop_hard_filter': True}),
    ('We do not need address components, but require rooftop-only precision.', {'address_elements_required': False, 'rooftop_hard_filter': True}),
])
def test_contrasting_requirements_do_not_share_polarity(query, expected):
    actual = {f['field']: f['value'] for f in extract_requirements({'query': query})}
    assert actual == expected


@pytest.mark.parametrize('query,field', [
    ('The provider docs say we need address components.', 'address_elements_required'),
    ('The API supports 20 stops per route.', 'max_stops'),
    ('Mapbox supports 20 stops per route.', 'max_stops'),
    ('Google allows 20 stops per route.', 'max_stops'),
    ('If we need address components and they only want rooftop precision, what is the cost?', 'rooftop_hard_filter'),
    ('The provider says it only accepts rooftop precision.', 'rooftop_hard_filter'),
])
def test_provider_capabilities_are_not_customer_requirements(query, field):
    assert field not in {f['field'] for f in extract_requirements({'query': query})}


@pytest.mark.parametrize('query,field,value,evidence', [
    ('The API supports 20 stops per route.', 'max_stops', 20, '20 stops per route'),
    ('The provider docs say we need address components.', 'address_elements_required', True, 'need address components'),
    ('We do not need address components.', 'address_elements_required', True, 'address components'),
])
def test_short_model_quote_cannot_hide_provider_or_negation_context(query, field, value, evidence):
    state = build_diagnostic_state({'query': query})
    plan = QualificationPlan.model_validate({'reason': 'Quoted evidence still needs context.', 'supplied_facts': [
        {'field': field, 'value': value, 'evidence': evidence}]})
    merge_model_facts(state, plan, {'query': query})
    assert field not in state.facts


def test_stale_provider_limit_cannot_hide_customer_route_size_question():
    enquiry = {'query': 'The API supports 20 stops per route. Recommend a provider.'}
    state = build_diagnostic_state(enquiry)
    state.facts['max_stops'] = DiagnosticFact(field='max_stops', value=20, source='query', evidence='20 stops per route')
    context_from_result(result_for(enquiry), state, enquiry)
    assert state.facts['max_stops'].status == 'missing'
