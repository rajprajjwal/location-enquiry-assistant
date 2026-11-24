"""Check that explanatory metadata cannot discard valid qualification groups."""
from pathlib import Path
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from copilot.diagnostics.facts import build_diagnostic_state
from copilot.qualification.contract import QualificationPlan
from copilot.qualification.facts import merge_model_facts
from copilot.qualification.validation import complete_plan, PlanValidationFailure
from copilot.model_gateway.reliability import Limits, query_session

MESSAGES = [{'role': 'user', 'content': 'Plan missing customer requirements.'}]


def response(value, finish='stop'):
    return SimpleNamespace(text=json.dumps(value), finish_reason=finish)


def captured():
    return json.loads((Path(__file__).parent / 'fixtures/qualification-long-reason.json').read_text())


def test_captured_reason_is_capped_locally_with_valid_facts_and_groups_intact():
    raw = captured()
    client = Mock()
    client.complete.return_value = response(raw)
    with query_session(Limits(max_retries_per_step=0)) as session:
        plan, audit = complete_plan(client, MESSAGES)
        assert session.retries == {}
    assert len(raw['reason']) == 620 and len(plan.reason) == 600
    expected = QualificationPlan.model_validate({**raw, 'reason': raw['reason'][:600]})
    assert plan.supplied_facts == expected.supplied_facts and plan.groups == expected.groups
    assert audit['status'] == 'locally_repaired' and client.complete.call_count == 1
    local = next(a for a in audit['attempts'] if a['stage'] == 'cap_diagnostic_reason')
    assert local['metadata_changes'] == [{'field': 'reason', 'original_length': 620, 'capped_length': 600}]
    assert local['response_sha256'] != audit['attempts'][0]['response_sha256']
    state = build_diagnostic_state({'query': 'Recommend a routing API.'})
    merge_model_facts(state, plan, {'query': 'Recommend a routing API.'})
    assert 'region' not in state.facts


def test_reason_at_boundary_is_preserved_without_local_repair():
    raw = {'reason': 'x' * 600, 'groups': [], 'supplied_facts': []}
    client = Mock()
    client.complete.return_value = response(raw)
    plan, audit = complete_plan(client, MESSAGES)
    assert plan.reason == raw['reason'] and audit['status'] == 'valid'


@pytest.mark.parametrize('reason', ['', None, 300])
def test_invalid_reason_type_or_empty_reason_is_not_fabricated(reason):
    client = Mock()
    client.complete.return_value = response({'reason': reason})
    with pytest.raises(PlanValidationFailure):
        complete_plan(client, MESSAGES)
    assert client.complete.call_count == 2


def test_truncated_completion_cannot_be_saved_by_capping_reason():
    client = Mock()
    client.complete.return_value = response(captured(), 'length')
    with pytest.raises(PlanValidationFailure) as caught:
        complete_plan(client, MESSAGES)
    assert all(a['stage'] in {'initial', 'repair'} for a in caught.value.audit['attempts'])


def test_reason_cap_and_invalid_fact_omission_revalidate_the_entire_plan():
    raw = captured()
    raw['supplied_facts'].append({'field': 'storage_required', 'value': True, 'evidence': ''})
    client = Mock()
    client.complete.return_value = response(raw)
    plan, audit = complete_plan(client, MESSAGES)
    assert audit['status'] == 'locally_repaired' and client.complete.call_count == 1
    assert len(plan.supplied_facts) == 1
    assert [a['stage'] for a in audit['attempts']] == ['initial', 'cap_diagnostic_reason', 'omit_unsupported_facts']


def test_remaining_group_errors_still_use_one_bounded_model_repair():
    raw = captured()
    raw['groups'][0]['fields'] = ['unknown_field']
    client = Mock()
    client.complete.return_value = response(raw)
    with pytest.raises(PlanValidationFailure) as caught:
        complete_plan(client, MESSAGES)
    assert client.complete.call_count == 2
    assert caught.value.audit['status'] == 'invalid_after_repair'
