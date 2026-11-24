"""An independent customer task must not inherit an earlier API incident."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

from copilot.diagnostics.facts import DiagnosticFact, DiagnosticQuestion, build_diagnostic_state
from copilot.diagnostics.planning import plan_staff_follow_up
from copilot.diagnostics.policy import allowed_decisions
from copilot.qualification.task import active_diagnostic_state, effective_customer_task


def result_for(enquiry, api='reverse_geocode', intent='pricing_quote'):
    return {'status': 'final', 'pending_reply': None,
            'clarifying_questions': {'needed': False, 'questions': []},
            'response_draft': {'draft_text': 'Review the documented answer.', 'citations': []},
            'outputs': {'qualification_details': {}, 'responsible_role': {'owner': 'Sales'},
                        'next_action': {'action_type': 'answer_directly'},
                        'proposed_record_update': {'applicable': False}},
            'diagnostic_context': {'state': build_diagnostic_state(enquiry).model_dump(),
                                   'interpretation': {'api': api, 'intent': intent},
                                   'retrieved_evidence': []}}


def client_for(decision='none'):
    client = Mock()

    def reply(messages, **options):
        payload = json.loads(messages[-1]['content'])
        body = {'supplied_facts': [], 'groups': [], 'reason': 'Use the active customer task.'} if payload.get('qualification_plan') else {
            'decision': decision, 'reason': 'Use the active observed failure.',
        }
        return SimpleNamespace(finish_reason='stop', text=json.dumps(body))

    client.complete.side_effect = reply
    return client


def test_requirement_supplement_carries_its_original_request():
    enquiry = {'query': 'Actually, we need live traffic.', 'history': [
        {'role': 'user', 'text': 'Recommend a Directions API for our delivery app.'},
        {'role': 'assistant', 'text': 'Use provider limits from documentation.'},
    ]}
    text = effective_customer_task(enquiry)
    assert 'Recommend a Directions API' in text and 'we need live traffic' in text
    assert 'Use provider limits' not in text


def test_a_supplied_fact_statement_does_not_need_a_special_continuation_phrase():
    enquiry = {'query': 'Our billing account is based in India.', 'history': [
        {'role': 'user', 'text': 'Compare Google Maps and Mapbox Directions prices.'},
    ]}
    task = effective_customer_task(enquiry)
    assert 'Compare Google Maps and Mapbox Directions prices.' in task
    assert 'billing account is based in India' in task


def test_account_fact_does_not_change_a_recommendation_task_into_a_quote():
    enquiry = {'query': 'Our billing account is based in India.', 'history': [
        {'role': 'user', 'text': 'Recommend a Directions API for our delivery app.'},
    ]}
    assert 'Recommend a Directions API' in effective_customer_task(enquiry)


def test_factual_prelude_is_retained_for_the_first_customer_request():
    enquiry = {'query': 'What should we ask before recommending a reverse-geocoding API?', 'history': [
        {'role': 'user', 'text': 'Addresses should be shown in Hindi. We must store results.'},
    ]}
    task = effective_customer_task(enquiry)
    assert 'Addresses should be shown in Hindi.' in task
    assert 'We must store results.' in task
    assert 'What should we ask' in task


def test_an_earlier_documentation_request_is_not_a_factual_prelude():
    enquiry = {'query': 'What should we ask before recommending a reverse-geocoding API?', 'history': [
        {'role': 'user', 'text': 'How do I set the language in Google reverse geocoding?'},
    ]}
    assert effective_customer_task(enquiry) == enquiry['query']


def test_factual_prelude_does_not_cross_an_explicit_api_change():
    enquiry = {'query': 'What should we ask before recommending a reverse-geocoding API?', 'history': [
        {'role': 'user', 'text': 'Our Directions API instructions should be shown in Hindi.'},
    ]}
    assert effective_customer_task(enquiry) == enquiry['query']


def test_what_else_qualification_continues_the_compatible_quote_task():
    from copilot.qualification.facts import context_from_result

    enquiry = {'query': 'What else should we ask before recommending a provider?', 'history': [
        {'role': 'user', 'text': 'Estimate monthly cost for Google Directions at 100,000 requests per month. We need live traffic.'},
    ]}
    task = effective_customer_task(enquiry)
    assert '100,000 requests per month' in task
    assert 'We need live traffic.' in task
    assert 'What else should we ask' in task
    state = build_diagnostic_state(enquiry)
    context = context_from_result(result_for(enquiry, api='directions', intent='sales_qualification'), state, enquiry)
    assert context.assumptions['monthly_volume'].value['requests_per_month'] == 100000
    assert context.facts['traffic_required'].value is True


def test_an_explicit_reference_preserves_scope_across_a_decision_kind_change():
    enquiry = {'query': 'For that request, what should we ask before recommending a provider?', 'history': [
        {'role': 'user', 'text': 'Estimate Google Directions for 100,000 requests per month.'},
    ]}
    assert '100,000 requests per month' in effective_customer_task(enquiry)


def test_what_else_cannot_override_an_explicit_new_topic():
    enquiry = {'query': 'New question: what else should we ask before recommending a provider?', 'history': [
        {'role': 'user', 'text': 'Estimate Google Directions for 100,000 requests per month.'},
    ]}
    assert effective_customer_task(enquiry) == enquiry['query']


def test_what_else_cannot_override_a_newly_named_api():
    enquiry = {'query': 'What else should we ask before recommending a reverse-geocoding API?', 'history': [
        {'role': 'user', 'text': 'Estimate Google Directions for 100,000 requests per month.'},
    ]}
    assert effective_customer_task(enquiry) == enquiry['query']


def test_explicit_new_topic_drops_old_api_failure_from_decision_context():
    enquiry = {'query': 'Switch topics. Estimate Mapbox reverse geocoding for 20,000 requests per month.',
               'history': [{'role': 'user', 'text': 'Our Google Directions request returns HTTP 401.'}]}
    state = build_diagnostic_state(enquiry)
    original = state.model_dump()
    active = active_diagnostic_state(state, enquiry, 'reverse_geocode')
    assert 'http_status' not in active.facts
    assert state.model_dump() == original
    assert allowed_decisions(state, enquiry['query'], 'reverse_geocode', enquiry=enquiry) == ['none']
    assert effective_customer_task(enquiry) == enquiry['query']


def test_newly_named_api_scopes_observations_even_without_topic_marker():
    enquiry = {'query': 'What does Mapbox reverse geocoding cost for 20,000 lookups a month?',
               'history': [{'role': 'user', 'text': 'Our Google Directions request returns HTTP 401.'}]}
    state = build_diagnostic_state(enquiry)
    assert allowed_decisions(state, enquiry['query'], 'reverse_geocode', enquiry=enquiry) == ['none']


def test_new_quote_on_same_api_is_separate_from_the_old_diagnostic_task():
    enquiry = {'query': 'Actually, estimate Google Directions for 20,000 requests per month.',
               'history': [{'role': 'user', 'text': 'Our Google Directions request returns HTTP 401.'}]}
    state = build_diagnostic_state(enquiry)
    assert allowed_decisions(state, enquiry['query'], 'directions', enquiry=enquiry) == ['none']


def test_same_failure_continuation_retains_the_observed_status():
    enquiry = {'query': 'Still failing after retrying.', 'history': [
        {'role': 'user', 'text': 'Our Google Directions request returns HTTP 401.'},
    ]}
    state = build_diagnostic_state(enquiry)
    active = active_diagnostic_state(state, enquiry, 'directions')
    assert active.facts['http_status'].value == ['401']
    assert allowed_decisions(state, enquiry['query'], 'directions', enquiry=enquiry) == ['request_reproduction']


def test_reopening_after_a_historical_topic_switch_keeps_the_new_scope():
    enquiry = {'query': 'Actually, use 30,000 lookups per month.', 'history': [
        {'role': 'user', 'text': 'Our Google Directions request returns HTTP 401.'},
        {'role': 'user', 'text': 'New question: estimate Mapbox reverse geocoding for 20,000 lookups per month.'},
    ]}
    state = build_diagnostic_state(enquiry)
    assert 'http_status' not in active_diagnostic_state(state, enquiry).facts
    assert allowed_decisions(state, enquiry['query'], 'reverse_geocode', enquiry=enquiry) == ['none']


def test_request_denied_continuation_keeps_original_observed_error_context():
    enquiry = {'query': 'Still failing after retrying.', 'history': [
        {'role': 'user', 'text': 'Our Google reverse geocoding request returns REQUEST_DENIED.'},
    ]}
    state = build_diagnostic_state(enquiry)
    assert allowed_decisions(state, enquiry['query'], 'reverse_geocode', enquiry=enquiry) == ['request_reproduction']


def test_old_request_evidence_does_not_satisfy_a_different_api_failure():
    enquiry = {'query': 'New question: our Mapbox reverse geocoding request returns HTTP 400.',
               'history': [{'role': 'user', 'text': 'Our Google Directions request returns HTTP 401. Request: /old/google/request'}]}
    state = build_diagnostic_state(enquiry)
    state.questions.append(DiagnosticQuestion(facts=['request_example'], text='Share the old request?', status='asked'))
    active = active_diagnostic_state(state, enquiry, 'reverse_geocode')
    assert 'request_example' not in active.facts
    assert not active.questions
    assert active.facts['http_status'].value == ['400']


def test_scope_fix_preserves_control_fields_and_audit_state():
    enquiry = {'query': 'Switch topics. Estimate Mapbox reverse geocoding for 20,000 requests per month.',
               'history': [{'role': 'user', 'text': 'Our Google Directions request returns HTTP 401.'}]}
    original = result_for(enquiry)
    before = deepcopy(original)
    updated = plan_staff_follow_up(original, enquiry, client=client_for())
    assert not any('failing request' in q['text'] for q in updated['outputs']['clarifying_questions']['questions'])
    assert updated['diagnostic_context']['state']['facts']['http_status']['value'] == ['401']
    for field in ('status', 'pending_reply', 'clarifying_questions'):
        assert updated[field] == before[field]
    for field in ('next_action', 'responsible_role', 'proposed_record_update'):
        assert updated['outputs'][field] == before['outputs'][field]


def test_prior_proceed_decision_does_not_silence_a_new_incident():
    enquiry = {'query': 'New question: our Mapbox reverse geocoding request returns HTTP 401.',
               'history': [{'role': 'user', 'text': 'Please proceed with what we know.'}]}
    result = result_for(enquiry, intent='troubleshooting')
    state = build_diagnostic_state(enquiry)
    assert state.facts['proceed_without_more_questions'].value is True
    assert 'proceed_without_more_questions' not in active_diagnostic_state(state, enquiry).facts
    updated = plan_staff_follow_up(result, enquiry, client=client_for())
    assert updated['follow_up_selection']['status'] == 'selected'
    assert 'request' in updated['outputs']['clarifying_questions']['questions'][0]['text']


def test_current_proceed_decision_still_suppresses_follow_ups():
    enquiry = {'query': 'Please proceed with what we know.',
               'history': [{'role': 'user', 'text': 'Our Google Directions request returns HTTP 401.'}]}
    client = client_for()
    updated = plan_staff_follow_up(result_for(enquiry, api='directions', intent='troubleshooting'), enquiry, client=client)
    assert updated['follow_up_selection']['status'] == 'declined'
    assert updated['outputs']['clarifying_questions']['questions'] == []
    client.complete.assert_not_called()
