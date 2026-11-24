"""Preserve explicitly requested billing scenarios without asserting actual usage."""
import pytest

from copilot.qualification.extraction import extract_requirements
from copilot.qualification.request_scope import request_constraints
from copilot.qualification.planning import plan_qualification
from tests.enquiry_workflow.test_qualification import result_for, client_for


@pytest.mark.parametrize('query,field,value', [
    ('Compare reverse-geocoding prices for 700,000 lookups per month (display only, no storage)?', 'storage_required', False),
    ('Ola vs Mapbox reverse geocoding when we must store 300,000 results a month?', 'storage_required', True),
    ('Compare prices for retaining 900000 responses each month.', 'storage_required', True),
    ('What would it cost if we need to cache 20,000 addresses?', 'storage_required', True),
    ('Compare pricing without result retention.', 'storage_required', False),
    ('Will Google bill our Autocomplete and the final Place Details call as one session?', 'details_completion', True),
    ('If our Autocomplete session ends with Place Details Pro, do we still pay for twelve requests?', 'details_completion', True),
    ('If our Autocomplete session ends with Place Details Pro, do we still pay for twelve requests?', 'details_sku', 'Place Details Pro'),
    ('Compare the cost of point-to-point driving routes.', 'travel_mode', 'driving'),
    ('What will two-wheeler routes via the Routes API cost?', 'travel_mode', 'two-wheeler'),
])
def test_requested_estimate_options_have_exact_provenance_and_types(query, field, value):
    assumption = request_constraints({'query': query})[field]
    assert assumption.value['value'] == value
    assert type(assumption.value['value']) is type(value)
    assert assumption.value['basis'] == 'requested_scope'
    assert query[assumption.start:assumption.end] == assumption.evidence
    assert field not in {fact['field'] for fact in extract_requirements({'query': query})}


@pytest.mark.parametrize('query,field', [
    ('Do we need to store addresses?', 'storage_required'),
    ('What would it cost if we might store addresses?', 'storage_required'),
    ('The docs say we must store results. What is the cost?', 'storage_required'),
    ('Does the documentation say we must store results to calculate prices?', 'storage_required'),
    ('Do we make a final Place Details call?', 'details_completion'),
    ('Does Autocomplete require the final Place Details call for billing?', 'details_completion'),
    ('The docs say sessions end with Place Details Pro. What is its cost?', 'details_completion'),
    ('We might end a session with Place Details Pro. What does it cost?', 'details_completion'),
    ('Compare routing costs for our bus aggregator app.', 'travel_mode'),
])
def test_unknown_usage_or_provider_instructions_do_not_become_requested_customer_options(query, field):
    assert field not in request_constraints({'query': query})
    assert field not in {fact['field'] for fact in extract_requirements({'query': query})}


@pytest.mark.parametrize('query,field,value', [
    ('We must store 300,000 results a month.', 'storage_required', True),
    ('We require retaining 300000 responses.', 'storage_required', True),
    ('We are caching 20000 addresses.', 'storage_required', True),
    ('Our results must be stored.', 'storage_required', True),
    ('We do not store any responses.', 'storage_required', False),
    ('We need display only, no storage.', 'storage_required', False),
    ('Our session ends with Place Details Pro.', 'details_completion', True),
    ('Our session ends with Place Details Pro.', 'details_sku', 'Place Details Pro'),
    ('We make the final Place Details call.', 'details_completion', True),
    ('We do not call Place Details.', 'details_completion', False),
    ('We need driving routes.', 'travel_mode', 'driving'),
])
def test_real_customer_requirements_remain_asserted_facts(query, field, value):
    facts = {fact['field']: fact for fact in extract_requirements({'query': query})}
    assert facts[field]['value'] == value
    assert type(facts[field]['value']) is type(value)
    fact = facts[field]
    assert query[fact['start']:fact['end']] == fact['evidence']


@pytest.mark.parametrize('query', [
    'If we must store 300,000 results, which API should we choose?',
    'We might store 300,000 results.',
    'The API requires storing results.',
    'The documentation says sessions end with Place Details Pro.',
    'If our session ends with Place Details Pro, how is it billed?',
])
def test_hypothetical_and_documentation_claims_never_become_actual_facts(query):
    assert not {'storage_required','details_completion','details_sku'} & {fact['field'] for fact in extract_requirements({'query': query})}


def test_explicit_negative_storage_scenario_is_not_reasked_even_if_the_model_selects_it():
    enquiry = {'query': 'Google vs Mapbox reverse geocoding for 500,000 lookups a month (display only, no storage)?'}
    result = result_for(enquiry)
    result['diagnostic_context']['interpretation'] = {'api':'reverse_geocode','intent':'pricing_comparison'}
    updated = plan_qualification(result, enquiry, client=client_for([
        {'fields':['storage_required'],'decision_impact':'Choose result-retention licensing.'},
    ]))
    assert not any('storage_required' in group['fields'] for group in updated['follow_up_selection'].get('groups', []))
    context = updated['diagnostic_context']['qualification']
    assert context['assumptions']['storage_required']['value']['value'] is False
    assert 'storage_required' not in context['facts']
