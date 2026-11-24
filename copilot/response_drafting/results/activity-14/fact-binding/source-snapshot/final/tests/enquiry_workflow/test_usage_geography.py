"""Keep operating geography explicit and separate from billing location."""
import pytest

from copilot.diagnostics.facts import build_diagnostic_state
from copilot.pricing_tools.qualification import explicit_geographies, comparison_qualification
from copilot.qualification.planning import plan_qualification
from tests.enquiry_workflow.test_qualification import result_for, client_for


@pytest.mark.parametrize('text,value', [
    ('Compare 12x8 matrices, 12,000 a month in India, with and without traffic.', 'India'),
    ('Quote 300 requests per month in Germany.', 'Germany'),
    ('Our app operates in India.', 'India'),
    ('Our app operates in India for deliveries.', 'India'),
    ('Our application runs in Germany.', 'Germany'),
    ('The service will operate in United States.', 'United States'),
    ('Our API is used in South Africa.', 'South Africa'),
    ('Our app will be used in New Zealand.', 'New Zealand'),
    ('We use the Mapbox API in Germany.', 'Germany'),
    ('We currently use Google Directions in India.', 'India'),
    ('Our application uses the routing API in India.', 'India'),
    ('Primary usage is India.', 'India'),
    ('Usage geography: Germany.', 'Germany'),
    ('Operating region is India.', 'India'),
    ('Primary usage is India and Germany.', 'India and Germany'),
])
def test_explicit_operating_usage_has_exact_customer_evidence(text, value):
    facts = [f for f in explicit_geographies(text) if f['field'] == 'usage_geography']
    assert facts and facts[-1]['value'] == value
    assert all(text[f['start']:f['end']] == f['evidence'] for f in facts)
    assert all(f['value'] in f['evidence'] for f in facts)


@pytest.mark.parametrize('text', [
    'Our billing country is India.',
    'Our company is based in India.',
    'Our office is in Germany.',
    'Our staff are in India.',
    'Our server runs in India.',
    'Our app does not operate in India.',
    'Our app will not operate in Germany.',
    'We do not use the routing API in India.',
    'Our app might operate in India.',
    'Our app may be used in Germany.',
    'Primary usage is not India.',
    'Usage geography is unknown.',
    'Primary usage is India or Germany.',
    'Could our app operate in India?',
    'Would 300 requests per month in India qualify?',
    'What if our app operates in India?',
    'Assuming our app operates in India, what is the rate?',
    'If our app operates in India, what is the cost?',
    'Can we use the routing API in India?',
    'If we use the Directions API in India and our app operates in Germany, what happens?',
    'The pricing guide says requests in India cost less.',
    'The documentation states primary usage is India.',
    'Google supports 300 requests per month in India.',
    'The API allows requests in India.',
])
def test_location_does_not_become_a_confirmed_usage_fact_without_assertion(text):
    assert not [f for f in explicit_geographies(text) if f['field'] == 'usage_geography']


def test_usage_and_billing_in_same_sentence_remain_distinct():
    text = 'Billing country is India and primary usage is Germany.'
    facts = {f['field']: f['value'] for f in explicit_geographies(text)}
    assert facts == {'billing_country': 'India', 'usage_geography': 'Germany'}


def test_billing_country_stops_at_the_next_workload_clause():
    text = 'Billing country is India and requests in Germany.'
    facts = {f['field']: f['value'] for f in explicit_geographies(text)}
    assert facts == {'billing_country': 'India', 'usage_geography': 'Germany'}


def test_unrelated_negative_billing_clause_does_not_hide_asserted_usage():
    text = 'Billing country is not India and primary usage is Germany.'
    facts = {f['field']: f['value'] for f in explicit_geographies(text)}
    assert facts == {'usage_geography': 'Germany'}


def test_explicit_customer_correction_uses_latest_usage_and_history_source():
    enquiry = {'query': 'Please estimate the cost.', 'history': [
        {'role': 'user', 'text': 'Primary usage is India.'},
        {'role': 'assistant', 'text': 'Your app operates in France.'},
        {'role': 'user', 'text': 'Correction: our app operates in Germany.'},
    ]}
    fact = build_diagnostic_state(enquiry).facts['usage_geography']
    assert fact.value == 'Germany' and fact.source == 'history[2]'
    assert 'France' not in fact.evidence


def test_workload_geography_reaches_planner_without_a_model_fact_proposal():
    enquiry = {'query': 'Compare Google and Ola Maps for 12x8 matrices, 12,000 a month in India, with and without traffic.'}
    original = result_for(enquiry)
    original['diagnostic_context']['interpretation'] = {'api': 'distance_matrix', 'intent': 'pricing_comparison'}
    original['diagnostic_context']['pricing_requirements'] = comparison_qualification(
        enquiry['query'], ['Google Maps Platform', 'Ola Maps'], 'India')
    result = plan_qualification(original, enquiry, client=client_for([]))
    assert result['diagnostic_context']['state']['facts']['usage_geography']['value'] == 'India'
    assert result['follow_up_selection']['groups'][0]['fields'] == ['billing_country']
    for key in ['status', 'pending_reply', 'clarifying_questions']:
        assert result[key] == original[key]
