"""The chat runner and UI must use the same persisted case controls."""
from contextlib import closing
import json
from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError

from copilot.case_storage import cases, sandbox
from copilot.case_storage.db import connect
from copilot.enquiry_workflow import cases as service
from copilot.enquiry_workflow.console import query_local
from copilot.model_gateway.client import LLMClient
from copilot.registered_tools.tool_registry import DocumentSearchTool
from copilot.response_drafting.schemas import validate_outputs
from tests.enquiry_workflow.test_escalation import parsed_for
from tests.support.helpers import completion


@pytest.fixture
def local_setup(monkeypatch):
    monkeypatch.setattr(service, 'interpret', lambda *a, **kw: parsed_for('How do I set waypoints?', 'docs_how_to'))
    monkeypatch.setattr(service, 'add_follow_up_questions', lambda result, *a, **kw: result)
    client = create_autospec(LLMClient, instance=True)

    def reply(messages, **kwargs):
        payload = json.loads(messages[-1]['content'])
        return completion('{"passage":1}' if 'passages' in payload else '{"answers_enquiry":true}')

    client.complete.side_effect = reply
    search = DocumentSearchTool(search_function=lambda _: [{
        'source_url': 'https://docs.example.com/waypoints',
        'relevant_passage': 'Add intermediate locations in the waypoints field.'}])
    return client, search


def test_chat_follow_up_preserves_pending_reply_and_reopens_formatted_response(tmp_path, local_setup):
    client, search = local_setup
    database = tmp_path / 'chat.db'
    first = query_local({'query': 'How do I set waypoints in the Directions API?', 'customer': 'Chat test'},
                        database=database, client=client, search=search)
    assert first['status'] == 'clarification_needed'
    assert 'Which map provider are you using?' in first['customer_response']['markdown']
    with closing(connect(database)) as con:
        assert cases.load_state(con, first['case_id'])['pending_clarification']['field'] == 'provider'
    second = query_local({'query': 'Mapbox', 'case_id': first['case_id']}, database=database, client=client, search=search)
    assert second['case_id'] == first['case_id'] and second['status'] == 'final'
    assert 'Add intermediate locations' in second['customer_response']['markdown']
    assert 'https://docs.example.com/waypoints' in second['customer_response']['markdown']
    with closing(connect(database)) as con:
        state = cases.load_state(con, first['case_id'])
        assert state['pending_clarification'] is None
        assert state['last_result']['customer_response'] == second['customer_response']
        assert validate_outputs(state['last_result']['outputs']) == []
        assert state['last_result']['outputs']['next_action']['executed'] is False


def test_chat_record_update_stays_pending_until_a_human_decides(tmp_path, local_setup):
    client, search = local_setup
    database = tmp_path / 'proposal.db'
    response = query_local({'query': 'Update sandbox ticket TKT-456. Set status to Investigating.'},
                           database=database, client=client, search=search)
    assert 'awaiting review' in response['customer_response']['markdown']
    with closing(connect(database)) as con:
        action, = cases.list_pending(con, response['case_id'])
        assert action['type'] == 'record_update'
        assert sandbox.get(con, 'TKT-456') == {}


def test_chat_request_rejects_fields_that_bypass_approval(tmp_path):
    with pytest.raises(ValidationError):
        query_local({'query': 'Update a ticket', 'approve': True}, database=tmp_path/'no-case.db')
    assert not (tmp_path/'no-case.db').exists()
