"""A bound status reply must affect its own turn and keep source-based replay."""
from contextlib import closing
from unittest.mock import Mock

import pytest

from copilot.case_storage import cases
from copilot.case_storage.db import connect
from copilot.enquiry_workflow import cases as service
from copilot.enquiry_workflow.case_memory import load_conversation
from copilot.enquiry_workflow.deletion import delete_enquiry
from copilot.enquiry_workflow.ownership_status import customer_status_reply
from copilot.registered_tools.tool_registry import DocumentSearchTool
from tests.enquiry_workflow.test_escalation import parsed_for
from tests.support.helpers import completion

QUERY = 'How do I set waypoints in Mapbox Directions?'
CHOICE = 'Are you a new or existing customer?'
POLAR = 'Are you an existing customer?'


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(service, 'interpret', lambda *a, **kw: parsed_for(QUERY, 'docs_how_to'))
    client = Mock()
    client.complete.return_value = completion('{"passages":[1],"answers_enquiry":true}')
    search = DocumentSearchTool(search_function=lambda _: [
        {'source_url': 'https://example.test/waypoints',
         'relevant_passage': 'Add intermediate locations in the waypoints field.'},
    ])
    return client, search


def pending_case(con, question=CHOICE):
    cid = cases.create_case(con)
    cases.add_message(con, cid, 'user', QUERY)
    cases.add_message(con, cid, 'clarification', question)
    cases.save_state(con, cid, {'pending_clarification': {'field': 'customer_status', 'task': QUERY}})
    return cid


def submit(con, configured, query, cid=None):
    client, search = configured
    return service.run_case(con, query, case_id=cid, client=client, search=search)


@pytest.mark.parametrize(('question', 'reply', 'expected', 'owner'), [
    (CHOICE, 'new', 'new', 'Account team (Sales)'),
    (CHOICE, 'existing', 'existing', 'Support L1'),
    (POLAR, 'yes', 'existing', 'Support L1'),
    (POLAR, 'no', 'new', 'Account team (Sales)'),
    ('Are you already using this service?', 'yes', 'existing', 'Support L1'),
    ('Are you already using this service?', 'no', 'new', 'Account team (Sales)'),
])
def test_actual_pending_status_reply_binds_before_routing(tmp_path, configured, question, reply, expected, owner):
    with closing(connect(tmp_path / 'cases.db')) as con:
        cid = pending_case(con, question)
        result = submit(con, configured, reply, cid)
        assert result['status'] == 'final'
        assert result['ownership_review']['customer_status'] == expected
        assert not result['ownership_review']['provisional']
        assert result['outputs']['responsible_role']['owner'] == owner
        assert result['conversation_state']['ownership_status']['customer_status'] == expected
        assert result['conversation_state']['ownership_status']['source'] == 'customer_message'
        assert cases.load_state(con, cid)['pending_clarification'] is None
        assert [row['content'] for row in cases.get_case_history(con, cid) if row['role'] == 'user'][-1] == reply


@pytest.mark.parametrize(('question', 'reply'), [
    (CHOICE, 'yes'), (CHOICE, 'no'),
    ('Are you an existing customer? What monthly volume do you expect?', 'yes'),
    ('Are you an existing customer, and which currency should I use?', 'existing'),
    ('Are you not an existing customer?', 'yes'),
    ('Which currency should I use?', 'new'),
    ('Is your Google Cloud project new?', 'yes'),
    ('', 'yes'),
])
def test_ambiguous_or_unrelated_short_answers_do_not_confirm(question, reply):
    assert customer_status_reply(reply, question, bound=True) is None


@pytest.mark.parametrize('bound', [False, True])
@pytest.mark.parametrize('reply', ['new', 'existing'])
@pytest.mark.parametrize('question', [
    'Is this a new or existing Google Cloud project?',
    'Is this a new or existing API key?',
    'Is this a new or existing account setup?',
    'Are you already using an existing API key?',
    'Are you already using a Google Cloud project?',
])
def test_setup_eligibility_questions_do_not_bind_customer_status(question, reply, bound):
    assert customer_status_reply(reply, question, bound=bound) is None


@pytest.mark.parametrize('reply', ['new', 'existing'])
def test_explicit_status_binding_without_question_accepts_literals(reply):
    assert customer_status_reply(reply, bound=True) == reply


@pytest.mark.parametrize('question', [
    CHOICE, POLAR, 'Are you already using this service?',
    'Are you already using Google Maps?',
    'Are you already using Google Maps through an existing account?',
])
def test_relationship_and_actual_service_use_questions_accept_literals(question):
    assert customer_status_reply('existing', question) == 'existing'


def test_an_ambiguous_pending_choice_does_not_manufacture_confirmation(tmp_path, configured, monkeypatch):
    seen = []
    actual = service.run_enquiry

    def capture(enquiry, *args, **kwargs):
        seen.append(enquiry['query'])
        return actual(enquiry, *args, **kwargs)

    monkeypatch.setattr(service, 'run_enquiry', capture)
    with closing(connect(tmp_path / 'cases.db')) as con:
        cid = pending_case(con)
        result = submit(con, configured, 'yes', cid)
        assert seen[-1] == 'yes'
        assert result['ownership_review']['customer_status'] == 'unknown'
        assert result['conversation_state']['ownership_status'] == {}


def test_status_deferral_remains_unknown_without_repeating_the_suggestion(tmp_path, configured):
    with closing(connect(tmp_path / 'cases.db')) as con:
        cid = pending_case(con)
        result = submit(con, configured, "Let's leave that open for now.", cid)
        assert result['ownership_review']['customer_status'] == 'unknown'
        assert result['ownership_review']['status_deferred']
        assert result['ownership_review']['suggested_question'] is None
        assert result['conversation_state']['ownership_status']['status_deferred']


def test_pending_confirmation_survives_reopen_and_is_isolated(tmp_path, configured):
    path = tmp_path / 'cases.db'
    with closing(connect(path)) as con:
        cid = pending_case(con)
        submit(con, configured, 'new', cid)
    with closing(connect(path)) as con:
        resumed = submit(con, configured, QUERY, cid)
        assert resumed['ownership_review']['customer_status'] == 'new'
        other = submit(con, configured, QUERY)
        assert other['ownership_review']['customer_status'] == 'unknown'
        assert other['case_id'] != cid


@pytest.mark.parametrize('reply', ['new', 'existing'])
def test_pending_status_without_assistant_question_persists_current_reply(tmp_path, configured, reply):
    path = tmp_path / 'cases.db'
    with closing(connect(path)) as con:
        cid = cases.create_case(con)
        cases.add_message(con, cid, 'user', QUERY)
        cases.save_state(con, cid, {'pending_clarification': {'field': 'customer_status', 'task': QUERY}})
        confirmed = submit(con, configured, reply, cid)
        assert confirmed['ownership_review']['customer_status'] == reply
        assert confirmed['conversation_state']['ownership_status']['customer_status'] == reply
        assert confirmed['conversation_state']['ownership_status']['source'] == 'customer_message'
        assert confirmed['conversation_state']['ownership_status']['reply_binding'] == 'pending_customer_status'
        assert [row['content'] for row in cases.get_case_history(con, cid) if row['role'] == 'user'][-1] == reply
    with closing(connect(path)) as con:
        reopened = submit(con, configured, QUERY, cid)
        assert reopened['ownership_review']['customer_status'] == reply
        delete_enquiry(con, confirmed['trace_id'])
        assert load_conversation(con, cid).ownership_status == {}
        after_delete = submit(con, configured, QUERY, cid)
        assert after_delete['ownership_review']['customer_status'] == 'unknown'


def test_deleting_the_only_confirmation_does_not_leak_status_through_later_turns(tmp_path, configured):
    with closing(connect(tmp_path / 'cases.db')) as con:
        cid = pending_case(con, POLAR)
        confirmed = submit(con, configured, 'yes', cid)
        later = submit(con, configured, QUERY, cid)
        assert later['ownership_review']['customer_status'] == 'existing'
        delete_enquiry(con, confirmed['trace_id'])
        assert load_conversation(con, cid).ownership_status == {}
        reopened = submit(con, configured, QUERY, cid)
        assert reopened['ownership_review']['customer_status'] == 'unknown'


def test_deleting_a_later_correction_restores_the_prior_confirmation(tmp_path, configured):
    with closing(connect(tmp_path / 'cases.db')) as con:
        cid = pending_case(con)
        submit(con, configured, 'existing', cid)
        cases.add_message(con, cid, 'clarification', CHOICE)
        state = cases.load_state(con, cid)
        cases.save_state(con, cid, {**state, 'pending_clarification': {'field': 'customer_status', 'task': QUERY}})
        corrected = submit(con, configured, 'new', cid)
        assert corrected['ownership_review']['customer_status'] == 'new'
        delete_enquiry(con, corrected['trace_id'])
        assert load_conversation(con, cid).ownership_status['customer_status'] == 'existing'


@pytest.mark.parametrize(('old_status', 'reply', 'owner'), [
    ('existing', 'new', 'Account team (Sales)'),
    ('new', 'existing', 'Support L1'),
])
def test_current_bound_reply_overrides_status_in_the_restored_old_task(tmp_path, configured, old_status, reply, owner):
    original = f'We are a {old_status} customer. {QUERY}'
    with closing(connect(tmp_path / 'cases.db')) as con:
        cid = cases.create_case(con)
        cases.add_message(con, cid, 'user', original)
        cases.add_message(con, cid, 'clarification', CHOICE)
        cases.save_state(con, cid, {'pending_clarification': {'field': 'customer_status', 'task': original}})
        corrected = submit(con, configured, reply, cid)
        assert corrected['ownership_review']['customer_status'] == reply
        assert corrected['outputs']['responsible_role']['owner'] == owner
        assert corrected['conversation_state']['ownership_status']['customer_status'] == reply
        restored = submit(con, configured, QUERY, cid)
        assert restored['ownership_review']['customer_status'] == reply
        delete_enquiry(con, corrected['trace_id'])
        assert load_conversation(con, cid).ownership_status == {}


def test_status_reply_keeps_the_underlying_incident_and_approval_route(tmp_path, configured, monkeypatch):
    incident = 'Production is down. Directions returns HTTP 503 for every request.'
    monkeypatch.setattr(service, 'interpret', lambda *a, **kw: parsed_for(incident, 'troubleshooting'))
    monkeypatch.setattr(service, 'add_follow_up_questions', lambda result, *a, **kw: result)
    with closing(connect(tmp_path / 'cases.db')) as con:
        cid = cases.create_case(con)
        cases.add_message(con, cid, 'user', incident)
        cases.add_message(con, cid, 'clarification', CHOICE)
        cases.save_state(con, cid, {'pending_clarification': {'field': 'customer_status', 'task': incident}})
        result = submit(con, configured, 'new', cid)
        assert result['ownership_review']['customer_status'] == 'new'
        assert result['status'] == 'escalated'
        assert result['outputs']['responsible_role']['owner'] == 'Maps engineering'
        assert result['proposed_actions'][0]['requires_human_approval']
        assert cases.list_pending(con, cid)[0]['status'] == 'pending'
