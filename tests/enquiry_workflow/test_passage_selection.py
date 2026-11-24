"""Verify bounded selection repair without accepting unsupported citation IDs."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from copilot.enquiry_workflow.passage_selection import select_passages
from copilot.enquiry_workflow.workflow import _draft, _review
from copilot.enquiry_workflow.verification.reliability_faults import Clock, FaultClient
from copilot.model_gateway.reliability import Limits, active_query, query_session, step_scope


def response(value, finish='stop'):
    return SimpleNamespace(text=value if isinstance(value, str) else json.dumps(value), finish_reason=finish)


def messages():
    return [{'role': 'system', 'content': 'Select at most three existing passage IDs.'},
            {'role': 'user', 'content': json.dumps({'enquiry': 'Explain the documented parameter.',
                'feedback': None, 'passages': [{'passage_id': i, 'relevant_passage': f'Parameter {i}.'} for i in range(1, 7)]})}]


def test_valid_and_explicit_unsupported_selections_do_not_retry():
    for value, expected in [({'passages': [2, 4]}, [2, 4]), ({'passages': []}, []), ({'passage': None}, [])]:
        client = Mock()
        client.complete.return_value = response(value)
        with query_session() as session:
            selected = select_passages(client, messages(), 6)
            assert session.retries == {}
        assert selected.indexes == expected and client.complete.call_count == 1


def test_too_many_valid_ids_get_one_repair_against_unchanged_candidates():
    original = messages()
    client = Mock()
    client.complete.side_effect = [response({'passages': [2, 4, 5, 6]}), response({'passages': [2, 5]})]
    with query_session() as session, step_scope('draft:3'):
        selected = select_passages(client, original, 6)
        assert session.retries == {'draft:3': 1}
    repaired = json.loads(client.complete.call_args.args[0][-1]['content'])
    assert 'at most 3' in repaired['feedback'] and 'outside' not in repaired['feedback']
    assert repaired['passages'] == json.loads(original[-1]['content'])['passages']
    assert repaired['enquiry'] == json.loads(original[-1]['content'])['enquiry']
    assert repaired['allowed_passage_ids'] == [1, 2, 3, 4, 5, 6]
    assert repaired['selection_repair'] is True
    assert selected.indexes == [2, 5] and selected.issue is None
    assert client.complete.call_count == 2
    assert all(call.kwargs['max_tokens'] == 256 for call in client.complete.call_args_list)


@pytest.mark.parametrize('value,error_type', [
    ({'passages': [7]}, 'id_range'),
    ({'passages': [True]}, 'id_type'),
    ({'passages': ['2']}, 'id_type'),
    ({'passages': '2'}, 'selection_type'),
    ({'unknown': [2]}, 'missing_selection'),
    ('{', 'invalid_json'),
])
def test_errors_are_distinguished_and_unrepaired_values_never_become_citations(value, error_type):
    client = Mock()
    client.complete.return_value = response(value)
    selected = select_passages(client, messages(), 6)
    assert selected.indexes is None and selected.error_type == error_type
    assert client.complete.call_count == 2


def test_truncated_selection_requires_repair_even_if_its_json_is_valid():
    client = Mock()
    client.complete.side_effect = [response({'passages': [2]}, 'length'), response({'passages': [4]})]
    selected = select_passages(client, messages(), 6)
    assert selected.indexes == [4]
    repaired = json.loads(client.complete.call_args.args[0][-1]['content'])
    assert 'truncated' in repaired['feedback']


def test_repaired_empty_selection_does_not_fabricate_an_answer():
    client = Mock()
    client.complete.side_effect = [response({'passages': [8]}), response({'passages': [], 'retry_query': '  parameter reference  '})]
    selected = select_passages(client, messages(), 6)
    assert selected.indexes == [] and selected.issue and selected.retry_query == 'parameter reference'
    assert client.complete.call_count == 2


@pytest.mark.parametrize('exhausted', [False, True])
def test_selection_repair_respects_existing_step_retry_credits(exhausted):
    def complete(*args, **kwargs):
        if exhausted:
            active_query().retry()
            active_query().retry()
        return response({'passages': [9]})
    client = Mock()
    client.complete.side_effect = complete
    limits = Limits(max_retries_per_step=2 if exhausted else 0)
    with query_session(limits), step_scope('draft:3'):
        selected = select_passages(client, messages(), 6)
    assert 'RetryLimitExceeded' in selected.issue and client.complete.call_count == 1


def test_expired_query_deadline_blocks_the_repair_call():
    clock = Clock()
    def complete(*args, **kwargs):
        clock.advance(2)
        return response({'passages': [9]})
    client = Mock()
    client.complete.side_effect = complete
    with query_session(Limits(enquiry_timeout_seconds=1), clock=clock):
        selected = select_passages(client, messages(), 6)
    assert 'DeadlineExceeded' in selected.issue and client.complete.call_count == 1


def test_real_gateway_token_budget_can_block_repair_without_another_transport():
    clock = Clock()
    client = FaultClient('persistent_invalid_json', clock)
    with query_session(Limits(token_budget=1000), clock=clock, sleeper=clock.advance) as session:
        selected = select_passages(client, messages(), 6)
        assert session.reserved_tokens <= 1000
    assert client.calls == 1 and 'BudgetExceeded' in selected.issue


def test_transport_and_selection_repair_share_two_credits():
    clock = Clock()
    client = FaultClient('healthy', clock)
    def once(*args, **kwargs):
        client.calls += 1
        if client.calls in {1, 3}:
            raise TimeoutError('Injected transport failure')
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"passages":[9]}', tool_calls=[]), finish_reason='stop')], model='test', usage=None)
    client._once = once
    with query_session(clock=clock, sleeper=clock.advance) as session, step_scope('draft:3'):
        selected = select_passages(client, messages(), 6)
        assert session.retries == {'draft:3': 2}
    assert client.calls == 3 and selected.issue


def test_draft_quotes_only_the_actual_repaired_passages_and_still_passes_grounding_review():
    passages = [{'source_url': f'https://example.test/doc/{i}', 'relevant_passage': f'Actual parameter {i}.'} for i in range(1, 7)]
    client = Mock()
    client.complete.side_effect = [response({'passages': [2, 4, 5, 6]}), response({'passages': [4, 2], 'invented_span': 'Fabricated answer.'})]
    draft, issue, _ = _draft(client, 'Explain the parameter.', passages, None)
    assert issue is None and _review(draft, passages) is None
    assert [c['span'] for c in draft['citations']] == ['Actual parameter 4.', 'Actual parameter 2.']
    assert 'Fabricated' not in draft['draft_text']


def test_repaired_selection_still_flows_through_the_graph_relevance_check():
    from copilot.enquiry_workflow.workflow import run_enquiry
    from copilot.registered_tools.tool_registry import DocumentSearchTool
    from tests.enquiry_workflow.test_workflow import support_case
    enquiry, interpretation = support_case()
    client = Mock()
    def complete(messages, **kwargs):
        payload = json.loads(messages[-1]['content'])
        if 'candidate' in payload:
            return response({'answers_enquiry': True})
        return response({'passages': [1] if payload.get('selection_repair') else [9]})
    client.complete.side_effect = complete
    result = run_enquiry(enquiry, interpretation, client=client,
        search=DocumentSearchTool(search_function=lambda _: [
            {'source_url': 'https://example.test/directions', 'relevant_passage': 'Use waypoints for intermediate locations.'}]))
    assert result['status'] == 'final' and result['step_count'] == 4
    assert result['critic']['verdict'] == 'pass'
    assert client.complete.call_count == 3
    assert result['response_draft']['citations'][0]['span'] == 'Use waypoints for intermediate locations.'
