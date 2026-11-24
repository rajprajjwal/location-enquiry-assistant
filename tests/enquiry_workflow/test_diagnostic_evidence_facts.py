"""Incident metadata requires customer assertions, exact evidence and explicit polarity."""
import pytest

from copilot.diagnostics.extraction import extract_supplied_facts
from copilot.diagnostics.facts import build_diagnostic_state
from copilot.qualification.task import active_diagnostic_state
from copilot.safety.pii import redact


def facts(query, history=None):
    return {fact['field']: fact for fact in extract_supplied_facts({'query': query, 'history': history or []})}


@pytest.mark.parametrize(('query', 'expected'), [
    ('No unusual usage spikes.', False),
    ('We have not observed any unusual traffic spikes.', False),
    ('We did not see unusual usage spikes.', False),
    ('Unexpected traffic spikes were not observed.', False),
    ('We noticed unexpected usage spikes.', True),
    ('We saw unusual usage spikes.', True),
    ('There were unusual traffic spikes.', True),
    ('Unusual usage spikes: no.', False),
    ('Unusual usage spikes: yes.', True),
])
def test_usage_observation_has_explicit_polarity_and_evidence(query, expected):
    actual = facts(query)['unusual_usage_spikes']
    assert actual['value'] is expected
    assert redact(query)[actual['start']:actual['end']] == actual['evidence']


@pytest.mark.parametrize('query', [
    'Any unusual usage spikes?',
    'Have you seen unusual usage spikes?',
    'If we observe unusual usage spikes, what should we do?',
    'We may have unusual usage spikes.',
    "We haven't checked for unusual usage spikes.",
    'We expect unusual traffic spikes.',
    'The documentation mentions unusual usage spikes.',
    'Unusual usage spikes: unknown.',
])
def test_questions_and_uncertainty_do_not_supply_a_boolean(query):
    assert 'unusual_usage_spikes' not in facts(query)


def test_latest_customer_observation_overrides_earlier_but_not_assistant_claims():
    result = facts('No unusual usage spikes.', [
        {'role': 'user', 'text': 'We observed unusual usage spikes.'},
        {'role': 'assistant', 'text': 'We observed unusual traffic spikes.'},
    ])
    assert result['unusual_usage_spikes']['value'] is False
    assert result['unusual_usage_spikes']['source'] == 'query'


def test_later_question_does_not_replace_an_observed_fact_with_an_inference():
    result = facts('Any unusual usage spikes?', [{'role': 'user', 'text': 'No unusual usage spikes.'}])
    assert result['unusual_usage_spikes']['value'] is False
    assert result['unusual_usage_spikes']['source'] == 'history[0]'


def test_explicit_incident_labels_keep_latest_source_and_exact_offsets():
    query = 'Account reference: ACCT-2; search query: hotel; returned prediction: Wrong Place; exposure time: yesterday; no unusual usage spikes.'
    result = facts(query, [{'role': 'user', 'text': 'Account reference: ACCT-1; exposure time: today'}])
    expected = {'account_reference': 'ACCT-2', 'prediction_query': 'hotel',
                'returned_prediction': 'Wrong Place', 'exposure_time': 'yesterday',
                'unusual_usage_spikes': False}
    for field, value in expected.items():
        assert result[field]['value'] == value
        assert result[field]['source'] == 'query'
        assert query[result[field]['start']:result[field]['end']] == result[field]['evidence']


@pytest.mark.parametrize('query', [
    'If account reference: ACCT-2, can you restore it?',
    'What is search query: hotel?',
    'The documentation gives returned prediction: Example Place.',
    'Maybe exposure time: yesterday.',
])
def test_context_guard_also_applies_to_labeled_incident_values(query):
    assert not {'account_reference', 'prediction_query', 'returned_prediction', 'exposure_time'} & facts(query).keys()


def test_new_incident_values_remain_redacted():
    token = 'abcdefghijklmnopqrstuvwxyz0123456789'
    query = f'Search query: hotel api_key={token}; returned prediction: contact person@example.com'
    result = facts(query)
    for field in ('prediction_query', 'returned_prediction'):
        actual = result[field]
        assert token not in str(actual)
        assert 'person@example.com' not in str(actual)
        assert redact(query)[actual['start']:actual['end']] == actual['evidence']


def test_new_incident_metadata_does_not_cross_task_boundaries():
    enquiry = {'query': 'New question: explain Mapbox Matrix limits.', 'history': [
        {'role': 'user', 'text': 'Account reference: ACCT-2; search query: hotel; returned prediction: Wrong Place; exposure time: yesterday; no unusual usage spikes.'},
    ]}
    state = build_diagnostic_state(enquiry)
    active = active_diagnostic_state(state, enquiry)
    for field in ('account_reference', 'prediction_query', 'returned_prediction', 'exposure_time', 'unusual_usage_spikes'):
        assert field in state.facts
        assert field not in active.facts
