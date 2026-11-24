"""Verify named authentication failures without changing enquiry routes."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from copilot.diagnostics.facts import build_diagnostic_state, DiagnosticQuestion
from copilot.diagnostics.planning import plan_staff_follow_up
from copilot.diagnostics.policy import allowed_decisions


@pytest.mark.parametrize('query', [
    'Google reverse geocoding gives REQUEST_DENIED when we add location_type=ROOFTOP.',
    'Google Geocode REQUEST_DENIED for reverse geocode with our Places-enabled key.',
    'Our reverse geocode request returns request_denied.',
])
def test_observed_named_denial_is_recognized(query):
    state = build_diagnostic_state({'query': query})
    assert state.facts['error_code'].value == 'REQUEST_DENIED'
    assert state.facts['error_code'].source == 'query'
    assert state.facts['error_code'].evidence.casefold() == 'request_denied'
    assert allowed_decisions(state, query, 'reverse_geocode') == ['request_reproduction']


@pytest.mark.parametrize('query', [
    'What does REQUEST_DENIED mean?',
    'What is REQUEST_DENIED?',
    'Explain the meaning of REQUEST_DENIED.',
    'Our request returns REQUEST_DENIED because we omitted the API key.',
    'Our request returns REQUEST_DENIED without our key.',
    'Our request returns REQUEST_DENIED. We have not enabled the Geocoding API.',
])
def test_documented_definition_or_confirmed_cause_needs_no_request(query):
    state = build_diagnostic_state({'query': query})
    assert allowed_decisions(state, query, 'reverse_geocode') == ['none']


def result_for(enquiry, state=None):
    return {
        'status': 'final', 'pending_reply': None,
        'clarifying_questions': {'needed': False, 'questions': []},
        'outputs': {'next_action': {'action_type': 'answer_directly'}, 'responsible_role': {'owner': 'Support L1'}},
        'diagnostic_context': {'state': (state or build_diagnostic_state(enquiry)).model_dump(mode='json'),
                               'retrieved_evidence': [{'source_url': 'https://docs.example.test',
                                   'relevant_passage': 'A missing API key is a possible reason for REQUEST_DENIED.'}]},
    }


def client_for_none():
    client = Mock()
    client.complete.return_value = SimpleNamespace(finish_reason='stop', text='{"decision":"none","reason":"A missing key may cause this."}')
    return client


def test_possible_documentation_cause_does_not_override_reported_failure():
    enquiry = {'query': 'Our reverse geocoding request returns REQUEST_DENIED.'}
    original = result_for(enquiry)
    updated = plan_staff_follow_up(original, enquiry, client=client_for_none())
    assert updated['follow_up_selection']['decision'] == 'request_reproduction'
    assert updated['follow_up_selection']['facts'] == ['request_example']
    assert 'credentials redacted' in updated['outputs']['clarifying_questions']['questions'][0]['text']
    for field in ['status', 'pending_reply', 'clarifying_questions']:
        assert updated[field] == original[field]
    for field in ['next_action', 'responsible_role']:
        assert updated['outputs'][field] == original['outputs'][field]


@pytest.mark.parametrize('condition', ['supplied', 'asked', 'declined'])
def test_request_is_not_repeated(condition):
    enquiry = {'query': 'Our reverse request returns REQUEST_DENIED.'}
    if condition == 'supplied':
        enquiry['query'] += '\nRequest URL: https://example.test/reverse?key=redacted'
    state = build_diagnostic_state(enquiry)
    if condition != 'supplied':
        state.questions.append(DiagnosticQuestion(facts=['request_example'], text='Share the redacted request?', status=condition))
    updated = plan_staff_follow_up(result_for(enquiry, state), enquiry, client=client_for_none())
    assert updated['outputs']['clarifying_questions']['questions'] == []


def test_assistant_history_does_not_supply_a_customer_failure():
    enquiry = {'query': 'How do I filter reverse results?',
               'history': [{'role': 'assistant', 'text': 'The API might return REQUEST_DENIED.'}]}
    state = build_diagnostic_state(enquiry)
    assert 'error_code' not in state.facts
    assert allowed_decisions(state, enquiry['query'], 'reverse_geocode') == ['none']
