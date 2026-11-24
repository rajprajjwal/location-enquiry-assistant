"""Provider alternatives must not silently become confirmed current service use."""
import pytest

from copilot.diagnostics.extraction import extract_supplied_facts
from copilot.diagnostics.facts import build_diagnostic_state
from copilot.enquiry_interpretation.postcheck import postcheck
from copilot.safety.provider_evidence import current_provider_hit
from tests.support.helpers import model_json


def facts(query, history=None):
    return {item['field']: item for item in extract_supplied_facts({'query': query, 'history': history or []})}


@pytest.mark.parametrize('query', [
    'Compare Google Maps and Mapbox Matrix.',
    'Compare Mapbox Matrix and Google Maps.',
])
def test_shortlist_preserves_both_names_without_a_chosen_provider(query):
    result = facts(query)
    assert set(result['mentioned_providers']['value']) == {'Google Maps Platform', 'Mapbox'}
    assert 'provider' not in result
    assert 'current_provider' not in result


@pytest.mark.parametrize('query', [
    'Is Mapbox Matrix supported?', 'Can we use Mapbox?', 'If we use Mapbox, what happens?',
    'We plan to use Mapbox.', 'We do not use Mapbox.', 'We used to use Mapbox.',
    'We are not a Mapbox customer.', 'We may be migrating from Mapbox to Google.',
    'Mapbox',
    'We use Google Maps and Mapbox.',
    'The docs say we use Mapbox for this example.',
    'We plan to use our Mapbox account next month.',
    'We use Google Maps for Directions and Mapbox for Matrix.',
    'If our Mapbox integration goes live, can we cache results?',
    'Suppose our Mapbox integration uses traffic.',
])
def test_mentions_and_possible_usage_do_not_confirm_a_current_provider(query):
    assert current_provider_hit(query) is None
    output = postcheck(model_json(qualification={
        'current_provider': {'value': 'Mapbox', 'evidence': 'Mapbox'},
    }), query=query)['output']
    assert output['qualification_details']['current_provider'] is None


@pytest.mark.parametrize(('query', 'expected'), [
    ('We use Google Maps and are considering Mapbox Matrix.', 'Google Maps Platform'),
    ('We are migrating from Google Maps to Mapbox.', 'Google Maps Platform'),
    ('We now use Mapbox.', 'Mapbox'),
    ('How can we fix our Mapbox integration?', 'Mapbox'),
    ('Our self-hosted OSRM returns HTTP 400.', 'OSRM'),
    ('Our 10×10 Google Distance Matrix request fails.', 'Google Maps Platform'),
    ('We switched to Mapbox last week and use it now.', 'Mapbox'),
    ('We migrated from Mapbox to Google last year.', 'Google Maps Platform'),
])
def test_asserted_relationship_is_distinct_from_an_alternative(query, expected):
    hit = current_provider_hit(query)
    assert hit['value'] == expected
    assert query[hit['start']:hit['end']] == hit['evidence']
    result = facts(query)
    assert result['current_provider']['value'] == expected


def test_support_target_can_be_known_while_current_provider_is_unknown():
    result = facts('Does Mapbox Matrix support traffic?')
    assert result['provider']['value'] == 'Mapbox'
    assert 'current_provider' not in result


def test_comparison_removes_stale_scalar_but_keeps_confirmed_current_provider():
    previous = build_diagnostic_state({'query': 'We use Google Maps.'})
    current = build_diagnostic_state({
        'query': 'Compare Mapbox and Ola Matrix.',
        'history': [{'role': 'user', 'text': 'We use Google Maps.'}],
    }, previous.model_dump())
    assert 'provider' not in current.facts
    assert current.facts['current_provider'].value == 'Google Maps Platform'
    assert current.facts['mentioned_providers'].value == ['Mapbox', 'Ola Maps']


def test_assistant_claim_does_not_establish_a_provider():
    assert facts('Please continue.', [{'role': 'assistant', 'text': 'You use Mapbox.'}]) == {}


def test_stored_provider_confirmation_beats_old_history_but_new_assertion_wins():
    enquiry = {'query': 'Please continue.', 'history': [{'role': 'user', 'text': 'We use Mapbox.'}],
               'known_facts': [{'field': 'current_provider', 'value': 'Google Maps Platform', 'source': 'history'}]}
    assert build_diagnostic_state(enquiry).facts['current_provider'].value == 'Google Maps Platform'
    enquiry['query'] = 'We now use Ola Maps.'
    assert build_diagnostic_state(enquiry).facts['current_provider'].value == 'Ola Maps'


def test_lowercase_here_is_not_a_provider_name():
    assert facts('We use the endpoint shown here.') == {}


@pytest.mark.parametrize('query', [
    'We no longer use Google Maps.',
    'We do not use Google Maps anymore; compare Mapbox and Ola.',
    'We use Google Maps for Directions and Mapbox for Matrix.',
])
def test_retraction_or_multiple_current_providers_clear_stale_scalar(query):
    history = [{'role': 'user', 'text': 'We use Google Maps.'}]
    enquiry = {'query': query, 'history': history,
               'known_facts': [{'field': 'current_provider', 'value': 'Google Maps Platform', 'source': 'history'}]}
    previous = build_diagnostic_state({'query': history[0]['text']})
    state = build_diagnostic_state(enquiry, previous.model_dump())
    assert 'current_provider' not in state.facts
    output = postcheck(model_json(qualification={
        'current_provider': {'value': 'Google', 'evidence': 'Google'},
    }), query=query, history=history, known_facts=enquiry['known_facts'])['output']
    assert output['qualification_details']['current_provider'] is None


def test_a_negative_mention_of_another_provider_does_not_revoke_current_use():
    result = facts('We do not use Mapbox.', [{'role': 'user', 'text': 'We use Google Maps.'}])
    assert result['current_provider']['value'] == 'Google Maps Platform'


def test_prospective_multi_provider_question_does_not_clear_current_use():
    history = [{'role': 'user', 'text': 'We use Ola Maps.'}]
    result = postcheck(model_json(), query='Should we use Google Maps and Mapbox?', history=history)['output']
    assert result['qualification_details']['current_provider'] == 'Ola Maps'


@pytest.mark.parametrize('query', [
    'All Ola reverse-geocode calls fail with 401/403 after we rotated credentials.',
    'Ola Distance Matrix returns 429 when our dispatcher refreshes ETAs.',
])
def test_reported_operations_bind_the_customer_provider(query):
    assert current_provider_hit(query)['value'] == 'Ola Maps'


def test_reopening_replays_a_historical_retraction_in_shared_state():
    enquiry = {'query': 'Please compare the options.', 'history': [
        {'role': 'user', 'text': 'We use Google Maps.'},
        {'role': 'user', 'text': 'We no longer use Google Maps.'},
    ], 'known_facts': [{'field': 'current_provider', 'value': 'Google Maps Platform', 'source': 'state_store'}]}
    assert 'current_provider' not in build_diagnostic_state(enquiry).facts


def test_bare_name_only_confirms_current_use_when_the_caller_binds_the_answer():
    from copilot.enquiry_workflow.case_memory import turn_event
    assert 'current_provider' not in turn_event('Mapbox')['facts']
    assert turn_event('Mapbox', facts={'current_provider': 'Mapbox'})['facts']['current_provider'] == 'Mapbox'


def test_legacy_history_retraction_survives_case_reopen(tmp_path):
    from contextlib import closing
    from copilot.case_storage import cases
    from copilot.case_storage.db import connect
    from copilot.enquiry_workflow.case_memory import load_conversation

    path = tmp_path / 'cases.db'
    with closing(connect(path)) as con:
        cid = cases.create_case(con)
        cases.add_message(con, cid, 'user', 'We use Google Maps.')
        cases.add_message(con, cid, 'user', 'We no longer use Google Maps.')
    with closing(connect(path)) as con:
        state = load_conversation(con, cid)
        assert 'current_provider' not in state.known_facts
        assert 'current_provider' not in state.diagnostic_state['facts']
