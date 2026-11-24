"""Add concrete handoff evidence without changing the selected workflow action."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from copilot.diagnostics.facts import DiagnosticFact, DiagnosticQuestion, build_diagnostic_state
from copilot.diagnostics.planning import plan_staff_follow_up
from copilot.diagnostics.policy import allowed_decisions

CREDIT = 'Our prepaid credits are exhausted and the API service stopped. Please restore the service.'
QUALITY = 'Our autocomplete returns harmful predictions. Please investigate the incorrect suggestions.'
EXPOSURE = 'Our production API key was leaked publicly in GitHub. Please investigate.'


def result_for(query, api='autocomplete'):
    return {'status': 'escalated', 'pending_reply': None,
            'clarifying_questions': {'needed': False, 'questions': []},
            'proposed_actions': [{'action_type': 'propose_escalation', 'approval_status': 'pending'}],
            'outputs': {'responsible_role': {'owner': 'Maps engineering', 'team': 'Support'},
                        'next_action': {'action_type': 'escalate', 'approval_status': 'pending'},
                        'proposed_record_update': {'applicable': False}},
            'diagnostic_context': {'state': build_diagnostic_state({'query': query}).model_dump(),
                                   'interpretation': {'api': api, 'intent': 'troubleshooting'},
                                   'retrieved_evidence': []}}


def client_for():
    client = Mock()
    client.complete.return_value = SimpleNamespace(finish_reason='stop', text=json.dumps({
        'decision': 'none', 'reason': 'Check the incident evidence.'}))
    return client


@pytest.mark.parametrize(('query', 'decision', 'fields'), [
    (CREDIT, 'credit_restoration', ['account_reference']),
    (QUALITY, 'prediction_quality', ['prediction_query', 'returned_prediction']),
    (EXPOSURE, 'credential_exposure', ['exposure_time', 'unusual_usage_spikes']),
])
def test_clear_incidents_publish_only_the_bound_evidence_fields(query, decision, fields):
    original = result_for(query)
    before = deepcopy(original)
    client = client_for()
    updated = plan_staff_follow_up(original, {'query': query}, client=client)
    assert updated['follow_up_selection']['decision'] == decision
    assert updated['follow_up_selection']['facts'] == fields
    assert client.complete.call_args.kwargs['max_tokens'] == 256
    assert client.complete.call_count == 1
    for field in ('status', 'pending_reply', 'clarifying_questions', 'proposed_actions'):
        assert updated[field] == before[field]
    for field in ('responsible_role', 'next_action', 'proposed_record_update'):
        assert updated['outputs'][field] == before['outputs'][field]


def test_credit_restoration_does_not_request_the_credential_value():
    updated = plan_staff_follow_up(result_for(CREDIT), {'query': CREDIT}, client=client_for())
    questions = updated['outputs']['clarifying_questions']['questions']
    assert len(questions) == 1
    assert 'account reference' in questions[0]['text']
    assert 'do not share credentials' in questions[0]['text']


def test_data_quality_requests_the_query_and_returned_prediction_together():
    updated = plan_staff_follow_up(result_for(QUALITY), {'query': QUALITY}, client=client_for())
    questions = updated['outputs']['clarifying_questions']['questions']
    assert len(questions) == 1
    assert 'exact search query' in questions[0]['text']
    assert 'prediction returned' in questions[0]['text']


def test_credential_exposure_has_two_independent_questions():
    updated = plan_staff_follow_up(result_for(EXPOSURE), {'query': EXPOSURE}, client=client_for())
    questions = updated['outputs']['clarifying_questions']['questions']
    assert len(questions) == 2
    assert questions[0]['field'] == 'exposure_time'
    assert questions[1]['field'] == 'unusual_usage_spikes'
    assert updated['follow_up_selection']['groups'][0]['fields'] == ['exposure_time']
    assert updated['follow_up_selection']['groups'][1]['fields'] == ['unusual_usage_spikes']


@pytest.mark.parametrize(('field', 'value', 'remaining'), [
    ('exposure_time', '2026-11-20 09:00 UTC', 'unusual_usage_spikes'),
    ('unusual_usage_spikes', False, 'exposure_time'),
])
def test_supplied_security_facts_suppress_only_their_own_question(field, value, remaining):
    original = result_for(EXPOSURE)
    original['diagnostic_context']['state']['facts'][field] = DiagnosticFact(
        field=field, value=value, source='query', evidence=EXPOSURE).model_dump()
    updated = plan_staff_follow_up(original, {'query': EXPOSURE}, client=client_for())
    assert [question['field'] for question in updated['outputs']['clarifying_questions']['questions']] == [remaining]


def test_provided_query_leaves_only_the_returned_prediction_request():
    original = result_for(QUALITY)
    original['diagnostic_context']['state']['facts']['prediction_query'] = DiagnosticFact(
        field='prediction_query', value='hotel', source='query', evidence=QUALITY).model_dump()
    updated = plan_staff_follow_up(original, {'query': QUALITY}, client=client_for())
    assert updated['follow_up_selection']['facts'] == ['returned_prediction']
    text = updated['outputs']['clarifying_questions']['questions'][0]['text']
    assert 'incorrect prediction' in text and 'exact autocomplete search query' not in text


def test_previously_asked_security_metadata_is_not_repeated():
    original = result_for(EXPOSURE)
    original['diagnostic_context']['state']['questions'] = [
        DiagnosticQuestion(facts=['exposure_time'], text='When was it exposed?', status='asked').model_dump(),
        DiagnosticQuestion(facts=['unusual_usage_spikes'], text='Any usage spikes?', status='declined').model_dump(),
    ]
    updated = plan_staff_follow_up(original, {'query': EXPOSURE}, client=client_for())
    assert updated['follow_up_selection']['status'] == 'facts_already_known'
    assert updated['outputs']['clarifying_questions']['questions'] == []


@pytest.mark.parametrize('query', [
    'What should we do if our API key leaks publicly?',
    'The documentation explains how an API key can leak publicly.',
    'If our credits are exhausted and the service stops, how can we restore it?',
    'Our credits are exhausted. How do we top up credits?',
    'Can autocomplete return harmful predictions?',
    'The docs mention wrong autocomplete predictions.',
    'Our autocomplete predictions were wrong, but we fixed the configuration.',
    'Our API key was not leaked publicly.',
    'Our API key has never been exposed publicly.',
    'Our autocomplete predictions are not harmful.',
    'Our autocomplete never returns wrong predictions.',
    'Our credits are not exhausted and the service stopped. Please restore it.',
    'Our credits are exhausted but the API service has not stopped. Please restore the service.',
    'Our credits are exhausted and the service stopped. Please do not restore it.',
])
def test_hypotheticals_documentation_and_known_remedies_do_not_gain_new_decisions(query):
    enquiry = {'query': query}
    decisions = allowed_decisions(build_diagnostic_state(enquiry), query, 'autocomplete', enquiry=enquiry)
    assert not {'credit_restoration', 'prediction_quality', 'credential_exposure'} & set(decisions)


def test_declined_followup_does_not_gain_security_questions():
    query = EXPOSURE + ' Please proceed with what we know.'
    client = client_for()
    updated = plan_staff_follow_up(result_for(query), {'query': query}, client=client)
    assert updated['follow_up_selection']['status'] == 'declined'
    assert updated['outputs']['clarifying_questions']['questions'] == []
    client.complete.assert_not_called()


def test_requesting_a_fix_does_not_mean_the_observed_problem_is_resolved():
    query = CREDIT + ' We want this fixed.'
    enquiry = {'query': query}
    assert allowed_decisions(build_diagnostic_state(enquiry), query, 'autocomplete', enquiry=enquiry) == ['credit_restoration']


def test_not_restored_is_not_misread_as_a_completed_restoration():
    query = 'Our credits are exhausted and the API service is down. It has not been restored. Please intervene.'
    enquiry = {'query': query}
    assert allowed_decisions(build_diagnostic_state(enquiry), query, 'autocomplete', enquiry=enquiry) == ['credit_restoration']
