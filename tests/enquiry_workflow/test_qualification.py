"""Check shared qualification semantics and unchanged workflow control state."""
from types import SimpleNamespace
from unittest.mock import Mock
import json

import pytest
from pydantic import ValidationError

from copilot.diagnostics.facts import build_diagnostic_state, DiagnosticQuestion
from copilot.qualification.contract import QualificationPlan
from copilot.qualification.facts import context_from_result, merge_model_facts
from copilot.qualification.planning import plan_qualification


def result_for(enquiry, active=None):
    questions = active or []
    return {'status':'final','pending_reply':None,'clarifying_questions':{'needed':bool(questions),'questions':questions},
        'outputs':{'qualification_details':{'region':'India','monthly_volume':None,'missing_required_fields':['monthly_volume']},
                   'next_action':{'action_type':'answer_directly'},'responsible_role':{'owner':'Sales'},
                   'proposed_record_update':{'applicable':False}},
        'diagnostic_context':{'state':build_diagnostic_state(enquiry).model_dump(mode='json'),
            'interpretation':{'api':'directions','intent':'sales_qualification'},'retrieved_evidence':[]}}


def client_for(groups, supplied=None):
    client=Mock()
    client.complete.return_value=SimpleNamespace(finish_reason='stop',text=json.dumps({'supplied_facts':supplied or [],'groups':groups,'reason':'Select requirements that change the recommendation.'}))
    return client


def test_contract_accepts_multiple_groups_and_rejects_unknown_fields():
    plan=QualificationPlan.model_validate({'groups':[{'fields':['monthly_volume'],'decision_impact':'Volume affects cost.'},{'fields':['traffic_required','travel_mode'],'decision_impact':'Features affect provider fit.'}],'reason':'Different decisions.'})
    assert len(plan.groups)==2
    with pytest.raises(ValidationError):
        QualificationPlan.model_validate({'groups':[{'fields':['invented_field'],'decision_impact':'Unknown.'}],'reason':'Unknown.'})


def test_full_interpretation_values_are_reused_without_changing_the_interpretation():
    enquiry={'query':'Recommend a routing API.'}; original=result_for(enquiry)
    state=build_diagnostic_state(enquiry)
    context=context_from_result(original,state,enquiry)
    assert context.facts['region'].value=='India'
    assert context.facts['region'].source=='interpretation'
    assert context.missing_interpretation_fields==['monthly_volume']
    assert original['outputs']['qualification_details']['monthly_volume'] is None


def test_independent_questions_do_not_change_route_owner_approval_or_pending():
    enquiry={'query':'Recommend a routing provider.'}; original=result_for(enquiry)
    updated=plan_qualification(original,enquiry,client=client_for([
        {'fields':['monthly_volume'],'decision_impact':'Determine monthly cost.'},
        {'fields':['traffic_required','travel_mode'],'decision_impact':'Determine routing support.'}]))
    assert len(updated['outputs']['clarifying_questions']['questions'])>=2
    for field in ['status','pending_reply','clarifying_questions']:
        assert updated[field]==original[field]
    for field in ['next_action','responsible_role','proposed_record_update']:
        assert updated['outputs'][field]==original['outputs'][field]


def test_active_question_is_enriched_only_in_staff_output():
    enquiry={'query':'What should we ask before recommending an API?'}
    original=result_for(enquiry,[{'field':'monthly_volume','text':'Monthly requests?'}])
    original['pending_reply']={'field':'monthly_volume','task':enquiry['query']}
    original['diagnostic_context']['interpretation']['api']='reverse_geocode'
    updated=plan_qualification(original,enquiry,client=client_for([
        {'fields':['monthly_volume','peak_rate'],'decision_impact':'Workload and peak load determine provider fit.'}]))
    assert updated['pending_reply']==original['pending_reply']
    assert updated['clarifying_questions']==original['clarifying_questions']
    q=updated['outputs']['clarifying_questions']['questions']
    assert q[0]['field']=='monthly_volume' and 'peak' in q[0]['text']


def test_supplied_sku_storage_and_traffic_are_not_repeated():
    enquiry={'query':'Sessions ending in Place Details Essentials. We must store addresses. We need live traffic.'}
    updated=plan_qualification(result_for(enquiry),enquiry,client=client_for([
        {'fields':['details_sku','storage_required','traffic_required'],'decision_impact':'Resolve requirements.'}]))
    assert updated['outputs']['clarifying_questions']['questions']==[]
    assert updated['diagnostic_context']['state']['facts']['details_sku']['value']=='Place Details Essentials'


def test_only_customer_evidence_can_establish_additional_facts():
    enquiry={'query':'We may store results.'}
    state=build_diagnostic_state(enquiry)
    plan=QualificationPlan.model_validate({'reason':'Uncertain and fabricated values are rejected.','supplied_facts':[
        {'field':'storage_required','value':True,'evidence':'may store'},
        {'field':'commercial_plan','value':'Enterprise','evidence':'We have an enterprise contract'}]})
    merge_model_facts(state,plan,enquiry)
    assert 'storage_required' not in state.facts and 'commercial_plan' not in state.facts


@pytest.mark.parametrize('status',['asked','declined'])
def test_asked_or_declined_fields_are_suppressed(status):
    enquiry={'query':'Recommend a routing provider.'}; original=result_for(enquiry)
    state=build_diagnostic_state(enquiry)
    state.questions.append(DiagnosticQuestion(facts=['traffic_required'],text='Traffic?',status=status))
    original['diagnostic_context']['state']=state.model_dump(mode='json')
    updated=plan_qualification(original,enquiry,client=client_for([
        {'fields':['traffic_required','travel_mode'],'decision_impact':'Choose routing features.'}]))
    assert any(group['fields']==['travel_mode'] for group in updated['follow_up_selection']['groups'])
    assert all('traffic_required' not in group['fields'] for group in updated['follow_up_selection']['groups'])


def test_explicit_no_is_preserved_as_supplied():
    enquiry={'query':'We do not store results.'}; state=build_diagnostic_state(enquiry)
    plan=QualificationPlan.model_validate({'reason':'Explicit customer answer.','supplied_facts':[
        {'field':'storage_required','value':False,'evidence':'do not store results'}]})
    merge_model_facts(state,plan,enquiry)
    assert state.facts['storage_required'].value is False


def test_proceed_does_not_create_new_questions_or_call_model():
    enquiry={'query':'Please proceed with what we know.','history':[{'role':'user','text':'Recommend an API.'}]}
    client=Mock()
    updated=plan_qualification(result_for(enquiry),enquiry,client=client)
    assert updated['outputs']['clarifying_questions']['questions']==[]
    client.complete.assert_not_called()


def test_planner_respects_the_shared_endpoint_output_cap():
    enquiry={'query':'Recommend an API.'}
    client=client_for([])
    plan_qualification(result_for(enquiry),enquiry,client=client)
    assert 0 < client.complete.call_args.kwargs['max_tokens'] <= 1024


def test_requirement_profiles_do_not_promote_generic_missing_fields():
    from copilot.qualification.contract import QualificationContext
    from copilot.qualification.requirements import applicable_groups
    context=QualificationContext(api='autocomplete',intent='pricing_quote',missing_interpretation_fields=['timeline','current_provider'])
    groups=applicable_groups(context,{'query':'Quote autocomplete for 200000 address-search sessions with 9 keystrokes each.'},{})
    assert {field for group in groups for field in group['fields']}=={'details_completion','debouncing'}


def test_omission_is_not_a_negative_answer():
    enquiry={'query':'We expect 150000 sessions with 12 keystrokes each.'}
    state=build_diagnostic_state(enquiry)
    plan=QualificationPlan.model_validate({'reason':'Missing information.','supplied_facts':[
        {'field':'details_completion','value':False,'evidence':enquiry['query']},
        {'field':'debouncing','value':False,'evidence':enquiry['query']}]})
    merge_model_facts(state,plan,enquiry)
    assert 'details_completion' not in state.facts and 'debouncing' not in state.facts


def test_language_does_not_establish_instruction_modality():
    enquiry={'query':'We need instructions in Hindi.'}; state=build_diagnostic_state(enquiry)
    plan=QualificationPlan.model_validate({'reason':'Language is not modality.','supplied_facts':[
        {'field':'instruction_modality','value':'text','evidence':enquiry['query']}]})
    merge_model_facts(state,plan,enquiry)
    assert 'instruction_modality' not in state.facts


def test_material_profile_facts_are_not_dropped_by_an_empty_model_group():
    enquiry={'query':'Our drivers need turn-by-turn instructions in Hindi.'}
    original=result_for(enquiry)
    original['diagnostic_context']['interpretation']['intent']='capability_match'
    updated=plan_qualification(original,enquiry,client=client_for([]))
    assert updated['follow_up_selection']['groups'][0]['fields']==['instruction_modality']


def test_split_model_groups_are_recombined_by_customer_decision():
    enquiry={'query':'What should we ask before recommending a reverse-geocoding API?'}
    original=result_for(enquiry)
    original['diagnostic_context']['interpretation']['api']='reverse_geocode'
    updated=plan_qualification(original,enquiry,client=client_for([
        {'fields':['peak_rate'],'decision_impact':'Peak scale.'},
        {'fields':['monthly_volume'],'decision_impact':'Recurring scale.'}]))
    groups=updated['follow_up_selection']['groups']
    assert any(set(group['fields'])=={'peak_rate','monthly_volume'} for group in groups)


@pytest.mark.parametrize('field',['input_type','max_stops'])
def test_false_is_not_a_value_for_count_or_representation(field):
    enquiry={'query':'Recommend an API for our app.'}; state=build_diagnostic_state(enquiry)
    plan=QualificationPlan.model_validate({'reason':'Unknown value.','supplied_facts':[
        {'field':field,'value':False,'evidence':enquiry['query']}]})
    merge_model_facts(state,plan,enquiry)
    assert field not in state.facts


def test_explicit_output_language_is_reused():
    enquiry={'query':'A logistics prospect wants addresses shown in Hindi, and may store results.'}
    state=build_diagnostic_state(enquiry)
    context=context_from_result(result_for(enquiry),state,enquiry)
    assert context.facts['languages'].value=='Hindi'


def test_customer_route_size_is_not_rejected_as_provider_documentation():
    enquiry={'query':'Recommend a routing API for our app.'}
    updated=plan_qualification(result_for(enquiry),enquiry,client=client_for([]))
    assert any('max_stops' in group['fields'] for group in updated['follow_up_selection']['groups'])


def test_requirement_scope_keeps_credential_protection():
    from copilot.response_drafting.question_filter import question_rejection
    assert question_rejection('Could you provide your API key?', customer_requirement=True)=='credential_value_requested'


def test_documentation_question_filter_keeps_its_default_behavior():
    from copilot.response_drafting.question_filter import question_rejection
    assert question_rejection('What is the maximum waypoint count supported by the API?')=='documentation_question'
