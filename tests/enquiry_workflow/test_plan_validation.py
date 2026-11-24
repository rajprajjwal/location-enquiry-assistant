"""Check bounded schema repair and shared gateway limits for qualification plans."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from copilot.qualification.validation import PlanValidationFailure, complete_plan
from copilot.diagnostics.planning import plan_staff_follow_up
from copilot.model_gateway.reliability import Limits, active_query, query_session
from copilot.enquiry_workflow.verification.reliability_faults import Clock, FaultClient
from tests.enquiry_workflow.test_qualification import result_for

MESSAGES=[{'role':'user','content':'Select a qualification plan for this working enquiry.'}]
VALID={'supplied_facts':[],'groups':[],'reason':'No unsupported facts are asserted.'}


def response(value, finish='stop'):
    return SimpleNamespace(text=value if isinstance(value,str) else json.dumps(value),finish_reason=finish)


def test_valid_plan_uses_one_call_and_no_retry():
    client=Mock();client.complete.return_value=response(VALID)
    with query_session() as session:
        plan,audit=complete_plan(client,MESSAGES)
        assert session.retries=={}
    assert plan.reason==VALID['reason'] and audit['status']=='valid'
    assert client.complete.call_count==1


def test_captured_empty_evidence_is_omitted_without_another_model_call():
    fixture=Path(__file__).parent/'fixtures/qualification-empty-evidence.json'
    invalid=json.loads(fixture.read_text())
    fixed={**invalid,'supplied_facts':[fact for fact in invalid['supplied_facts'] if fact['evidence']]}
    client=Mock();client.complete.side_effect=[response(invalid),response(fixed)]
    with query_session() as session:
        plan,audit=complete_plan(client,MESSAGES)
        assert session.retries=={}
    assert audit['status']=='locally_repaired' and len(audit['attempts'])==2
    assert client.complete.call_count==1
    error=audit['attempts'][0]['errors'][0]
    assert error['loc']==['supplied_facts',0,'evidence'] and error['type']=='string_too_short'
    assert 'input' not in error
    assert all(f.field!='region' for f in plan.supplied_facts)
    assert plan.groups==__import__('copilot.qualification.contract',fromlist=['QualificationPlan']).QualificationPlan.model_validate(fixed).groups
    assert audit['attempts'][1]['dropped_facts'][0]['index']==0
    assert all(call.kwargs['max_tokens']<=1024 for call in client.complete.call_args_list)


def test_invalid_json_has_one_repair_and_then_stops():
    client=Mock();client.complete.return_value=response('{')
    with pytest.raises(PlanValidationFailure) as error:
        complete_plan(client,MESSAGES)
    assert client.complete.call_count==2
    assert error.value.audit['status']=='invalid_after_repair'
    assert len(error.value.audit['attempts'])==2


def test_truncation_is_not_accepted_as_a_valid_plan():
    client=Mock();client.complete.side_effect=[response(VALID,'length'),response(VALID)]
    _,audit=complete_plan(client,MESSAGES)
    assert audit['status']=='repaired'
    assert audit['attempts'][0]['errors'][0]['type']=='completion_truncated'


@pytest.mark.parametrize('exhausted',[False,True])
def test_schema_repair_respects_shared_retry_credits(exhausted):
    def initial(*args,**kwargs):
        if exhausted:
            active_query().retry();active_query().retry()
        return response('{')
    client=Mock();client.complete.side_effect=initial
    with query_session(Limits(max_retries_per_step=2 if exhausted else 0)) as session:
        with pytest.raises(PlanValidationFailure) as error:
            complete_plan(client,MESSAGES)
        assert session.retries==({'qualification_plan':2} if exhausted else {})
    assert client.complete.call_count==1
    assert not error.value.audit['repair_attempted']
    assert error.value.audit['error_type']=='RetryLimitExceeded'


def test_expired_deadline_blocks_repair():
    clock=Clock()
    def initial(*args,**kwargs):
        clock.advance(2);return response('{')
    client=Mock();client.complete.side_effect=initial
    with query_session(Limits(enquiry_timeout_seconds=1),clock=clock):
        with pytest.raises(PlanValidationFailure) as error:
            complete_plan(client,MESSAGES)
    assert client.complete.call_count==1
    assert error.value.audit['error_type']=='DeadlineExceeded'


def test_real_gateway_token_reservations_bound_repair_without_transport():
    clock=Clock();client=FaultClient('persistent_invalid_json',clock)
    with query_session(Limits(token_budget=2000),clock=clock,sleeper=clock.advance) as session:
        with pytest.raises(PlanValidationFailure) as error:
            complete_plan(client,MESSAGES)
        assert session.reserved_tokens<=2000
    assert client.calls==1
    assert error.value.audit['error_type']=='BudgetExceeded'


def test_failed_repair_keeps_active_question_route_and_pending_without_third_call():
    enquiry={'query':'Recommend a routing API.'}
    original=result_for(enquiry,[{'field':'region','text':'Where will the application operate?'}])
    original['status']='clarification_needed';original['pending_reply']={'field':'region','task':enquiry['query']}
    client=Mock();client.complete.return_value=response('{')
    updated=plan_staff_follow_up(original,enquiry,client=client)
    assert client.complete.call_count==2
    assert updated['qualification_plan_error']=='PlanValidationFailure'
    assert updated['qualification_plan_validation']['status']=='invalid_after_repair'
    for field in ['status','pending_reply','clarifying_questions']:
        assert updated[field]==original[field]
    for field in ['next_action','responsible_role','proposed_record_update']:
        assert updated['outputs'][field]==original['outputs'][field]
    assert updated['outputs']['clarifying_questions']==original['clarifying_questions']


def test_repair_cannot_persist_an_invented_country_quote():
    enquiry={'query':'Recommend routing for 20000 requests per month.'}
    original=result_for(enquiry);original['outputs']['qualification_details']['region']=None
    invalid={'supplied_facts':[{'field':'region','value':'India','evidence':''}],'groups':[],'reason':''}
    fixed={'supplied_facts':[{'field':'region','value':'India','evidence':'India'}],'groups':[],'reason':'Claimed region.'}
    client=Mock();client.complete.side_effect=[response(invalid),response(fixed)]
    updated=plan_staff_follow_up(original,enquiry,client=client)
    assert updated['qualification_plan_validation']['status']=='repaired'
    assert 'region' not in updated['diagnostic_context']['state']['facts']


def test_pricing_metadata_cannot_bypass_an_earlier_policy_override():
    enquiry={'query':'Recommend a routing API; our API key is invalid.'}
    original=result_for(enquiry)
    original['diagnostic_context']['pricing_requirements']={'applicable':True,'required_facts':['billing_country'],'reason':'Pricing eligibility.'}
    client=Mock();client.complete.return_value=response('{')
    updated=plan_staff_follow_up(original,enquiry,client=client)
    assert client.complete.call_count==2
    assert updated['follow_up_selection']['status']=='qualification_validation_fallback'


def test_transport_and_schema_repair_together_use_at_most_two_retry_credits():
    clock=Clock();client=FaultClient('healthy',clock)
    def once(*args,**kwargs):
        client.calls+=1
        if client.calls in {1,3}:
            raise TimeoutError('Injected transport failure')
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{',tool_calls=[]),finish_reason='stop')],model='test-model',usage=None)
    client._once=once
    with query_session(clock=clock,sleeper=clock.advance) as session:
        with pytest.raises(PlanValidationFailure) as error:
            complete_plan(client,MESSAGES)
        assert session.retries=={'qualification_plan':2}
    assert client.calls==3
    assert error.value.audit['logical_requests']==2
    assert error.value.audit['repair_attempted']


def test_local_omission_can_recover_with_no_retry_credit():
    fixture=Path(__file__).parent/'fixtures/qualification-empty-evidence.json'
    client=Mock();client.complete.return_value=response(fixture.read_text())
    with query_session(Limits(max_retries_per_step=0)) as session:
        _,audit=complete_plan(client,MESSAGES)
        assert session.retries=={}
    assert audit['status']=='locally_repaired' and client.complete.call_count==1


def test_other_invalid_contract_fields_still_need_repair_after_fact_omission():
    invalid={'supplied_facts':[{'field':'region','value':'India','evidence':''}], 'groups':[], 'reason':''}
    client=Mock();client.complete.side_effect=[response(invalid),response(VALID)]
    with query_session() as session:
        plan,audit=complete_plan(client,MESSAGES)
        assert session.retries=={'qualification_plan':1}
    assert audit['status']=='repaired' and audit['local_repair_attempted']
    assert len(audit['attempts'])==3
    payload=json.loads(client.complete.call_args.args[0][-1]['content'])
    assert 'Do not add customer facts or invent evidence' in payload['instructions']
    assert json.loads(client.complete.call_args.args[0][-2]['content'])['supplied_facts']==[]
