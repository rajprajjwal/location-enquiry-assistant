"""Check that recognized provider replies resolve the active question once."""
from contextlib import closing
import json
from unittest.mock import Mock

import pytest

from copilot.case_storage import cases
from copilot.case_storage.db import connect
from copilot.enquiry_workflow.cases import run_case
from copilot.enquiry_workflow.providers import resolve_provider
from copilot.registered_tools.tool_registry import DocumentSearchTool
from tests.support.helpers import completion, model_json

QUERY = (
    'We need to turn GPS coordinates into a human-readable address, optionally filtered to rooftop '
    'precision, with a language preference and a controllable level of address detail. '
    'What do Google Reverse Geocoding, Nominatim Reverse, Ola Reverse Geocode, and Mapbox Geocoding document?'
)


def _setup():
    def answer(messages, **_options):
        prompt = messages[-1]['content']
        if '"qualification_plan"' in prompt:
            return completion(json.dumps({'supplied_facts': [], 'groups': [], 'reason': 'No additional requirements.'}))
        if '"passages"' in prompt:
            return completion('{"passages":[1]}')
        if '"candidate"' in prompt:
            return completion('{"answers_enquiry":true}')
        return completion(model_json(intent='docs_how_to', sub_intent='parameter_question',
                                     api='reverse_geocode', team='Support'))
    client = Mock()
    client.complete.side_effect = answer
    search = DocumentSearchTool(search_function=lambda _: [
        {'source_url': 'https://docs.mapbox.com/api/search/geocoding/',
         'relevant_passage': 'Use language to request a preferred language in reverse geocoding.'},
    ])
    return client, search


@pytest.mark.parametrize('pending_field', ['provider', 'current_provider'])
def test_recognized_reply_resolves_both_pending_provider_aliases_on_reopen(tmp_path, pending_field):
    path = tmp_path / 'cases.db'
    client, search = _setup()
    with closing(connect(path)) as con:
        first = run_case(con, QUERY, client=client, search=search)
        assert first['status'] == 'clarification_needed'
        state = cases.load_state(con, first['case_id'])
        assert state['pending_clarification']['field'] == 'provider'
        state['pending_clarification']['field'] = pending_field
        cases.save_state(con, first['case_id'], state)

    with closing(connect(path)) as con:
        second = run_case(con, 'Mapbox', case_id=first['case_id'], client=client, search=search)
        assert second['status'] == 'final'
        assert second['clarifying_questions']['questions'] == []
        assert cases.load_state(con, first['case_id'])['pending_clarification'] is None
        memory = second['conversation_state']
        assert memory['known_facts']['current_provider'] == 'Mapbox'
        assert memory['questions_answered'] == ['current_provider']
        assert memory['unresolved_issues'] == []
        assert memory['diagnostic_state']['facts']['provider']['value'] == 'Mapbox'
        assert memory['diagnostic_state']['facts']['current_provider']['value'] == 'Mapbox'
        clarification = [m for m in cases.get_case_history(con, first['case_id']) if m['role'] == 'clarification']
        assert len(clarification) == 1
        assert second['outputs']['responsible_role'] == first['outputs']['responsible_role']
        assert second['proposed_actions'] == first['proposed_actions'] == []


def test_multiple_named_providers_are_not_disambiguated_by_generic_history(tmp_path):
    assert resolve_provider(QUERY, [{'role': 'user', 'text': 'We use Mapbox.'}]) is None
    client, search = _setup()
    with closing(connect(tmp_path / 'cases.db')) as con:
        cid = cases.create_case(con)
        cases.add_message(con, cid, 'user', 'We use Mapbox.')
        result = run_case(con, QUERY, case_id=cid, client=client, search=search)
        assert result['status'] == 'clarification_needed'
        assert result['clarifying_questions']['questions'][0]['field'] == 'provider'
        assert cases.load_state(con, cid)['pending_clarification']['field'] == 'provider'


def test_provider_confirmation_does_not_leak_to_another_case(tmp_path):
    client, search = _setup()
    with closing(connect(tmp_path / 'cases.db')) as con:
        first = run_case(con, QUERY, client=client, search=search)
        run_case(con, 'Mapbox', case_id=first['case_id'], client=client, search=search)
        other = run_case(con, QUERY, client=client, search=search)
        assert other['case_id'] != first['case_id']
        assert other['status'] == 'clarification_needed'
        assert other['clarifying_questions']['questions'][0]['field'] == 'provider'


def test_ambiguous_reply_does_not_confirm_one_of_its_providers(tmp_path, monkeypatch):
    from copilot.enquiry_workflow import cases as workflow_cases

    wrapped = Mock(wraps=workflow_cases.run_enquiry)
    monkeypatch.setattr(workflow_cases, 'run_enquiry', wrapped)
    client, search = _setup()
    with closing(connect(tmp_path / 'cases.db')) as con:
        first = run_case(con, QUERY, client=client, search=search)
        second = run_case(con, 'Mapbox or Google', case_id=first['case_id'], client=client, search=search)
        assert wrapped.call_args.kwargs['confirmed_provider'] is None
        assert second['status'] == 'clarification_needed'
        assert cases.load_state(con, first['case_id'])['pending_clarification']['field'] == 'provider'


def test_explicit_pending_answer_replaces_a_previous_provider_fact(tmp_path):
    client, search = _setup()
    with closing(connect(tmp_path / 'cases.db')) as con:
        cid = cases.create_case(con)
        cases.add_message(con, cid, 'user', 'We use Mapbox.')
        first = run_case(con, QUERY, case_id=cid, client=client, search=search)
        second = run_case(con, 'Google Maps', case_id=cid, client=client, search=search)
        assert first['status'] == 'clarification_needed'
        assert second['status'] == 'final'
        assert second['conversation_state']['known_facts']['current_provider'] == 'Google Maps Platform'
        assert second['conversation_state']['diagnostic_state']['facts']['current_provider']['value'] == 'Google Maps Platform'
        assert cases.load_state(con, cid)['pending_clarification'] is None
