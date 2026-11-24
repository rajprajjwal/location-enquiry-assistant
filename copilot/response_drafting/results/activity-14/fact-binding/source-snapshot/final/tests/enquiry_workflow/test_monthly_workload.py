"""Verify workload usability, units and qualification control invariants."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from copilot.diagnostics.facts import DiagnosticFact, DiagnosticQuestion, build_diagnostic_state
from copilot.qualification.contract import QualificationPlan
from copilot.qualification.facts import context_from_result, merge_model_facts
from copilot.qualification.planning import plan_qualification
from copilot.qualification.workload import normalize_monthly_volume, from_text


@pytest.mark.parametrize('raw,count,unit',[
    ('20,000 requests per month',20000,'requests_per_month'),
    ('1.5M lookups/month',1500000,'lookups_per_month'),
    ('150,000 sessions a month',150000,'sessions_per_month'),
    ('120,000 elements per month',120000,'elements_per_month'),
    ('0 calls per month',0,'calls_per_month'),
    ('500,000 address-search sessions a month',500000,'sessions_per_month'),
    ('Monthly usage: 2.5 lakh requests',250000,'requests_per_month'),
    ('500 matrices per month',500,'matrices_per_month'),
    ('10x10 matrices, 5,000 per month',5000,'matrices_per_month'),
    ("Ola Distance Matrix: send 10 origins x 5 destinations about 2,000 times a month",2000,'matrices_per_month'),
])
def test_monthly_workload_keeps_count_and_stated_unit(raw,count,unit):
    value=from_text(raw)
    assert value['requests_per_month']==count
    assert value['unit']==unit


@pytest.mark.parametrize('value',[
    {'raw':'15–20 outlets','requests_per_month':None,'unit':None},
    {'raw':'20 outlets','requests_per_month':20,'unit':'requests_per_month'},
    {'raw':'20,000','requests_per_month':20000,'unit':'per_month'},
    {'raw':'20,000 requests per day','requests_per_month':20000,'unit':'requests_per_month'},
    {'raw':'15–20 requests/month','requests_per_month':20,'unit':'requests_per_month'},
    '50 requests/second', '20000', '15–20 outlets',
    '-20 requests per month', '-20 matrices per month',
    {'raw':'20000','requests_per_month':float('inf'),'unit':'requests_per_month'},
    {'raw':'1','requests_per_month':True,'unit':'requests_per_month'},
])
def test_incomplete_or_conflicting_quantity_is_not_supplied(value):
    assert normalize_monthly_volume(value) is None


def result_for(enquiry, volume):
    return {'status':'final','pending_reply':None,'clarifying_questions':{'needed':False,'questions':[]},
        'outputs':{'qualification_details':{'monthly_volume':volume,'missing_required_fields':[]},
            'next_action':{'action_type':'answer_directly'},'responsible_role':{'owner':'Sales'},
            'proposed_record_update':{'applicable':False}},
        'diagnostic_context':{'state':build_diagnostic_state(enquiry).model_dump(mode='json'),
            'interpretation':{'api':'directions','intent':'sales_qualification'},'retrieved_evidence':[]}}


def client_for(proposals=None):
    client=Mock()
    client.complete.return_value=SimpleNamespace(finish_reason='stop',text=json.dumps({
        'supplied_facts':proposals or [],'groups':[],'reason':'Check the applicable requirements.'}))
    return client


def test_bad_interpretation_and_model_proposal_cannot_hide_monthly_question():
    enquiry={'query':"Recommend a routing API for daily beat plans with 15–20 outlets."}
    partial={'raw':'15–20 outlets','requests_per_month':None,'unit':None}
    original=result_for(enquiry,partial);before=deepcopy(original)
    updated=plan_qualification(original,enquiry,client=client_for([
        {'field':'monthly_volume','value':'15–20 outlets','evidence':'15–20 outlets'}]))
    assert any('monthly_volume' in group['fields'] for group in updated['follow_up_selection']['groups'])
    assert updated['outputs']['qualification_details']==before['outputs']['qualification_details']
    for field in ['status','pending_reply','clarifying_questions']:
        assert updated[field]==before[field]
    for field in ['next_action','responsible_role','proposed_record_update']:
        assert updated['outputs'][field]==before['outputs'][field]


def test_stale_partial_state_is_invalidated_without_answering_pending_question():
    enquiry={'query':'We have 15–20 outlets.'};partial={'raw':'15–20 outlets','requests_per_month':None,'unit':None}
    state=build_diagnostic_state(enquiry)
    state.facts['monthly_volume']=DiagnosticFact(field='monthly_volume',value=partial,source='state_store')
    state.questions.append(DiagnosticQuestion(facts=['monthly_volume'],text='Monthly requests?',status='asked'))
    context=context_from_result(result_for(enquiry,partial),state,enquiry)
    assert context.facts['monthly_volume'].status=='missing'
    assert state.questions[0].status=='asked'


def test_explicit_volume_is_recovered_and_preserves_stops_separately():
    enquiry={'query':'Recommend routing for 15–20 outlets per route and 20,000 requests per month.'}
    result=result_for(enquiry,{'raw':'15–20 outlets','requests_per_month':None,'unit':None})
    state=build_diagnostic_state(enquiry);context=context_from_result(result,state,enquiry)
    assert context.facts['monthly_volume'].value['requests_per_month']==20000
    assert context.facts['monthly_volume'].value['unit']=='requests_per_month'
    assert state.facts['max_stops'].value=='15–20'


def test_valid_normalized_stored_quantity_remains_supplied():
    value={'raw':'20k','requests_per_month':20000,'unit':'requests_per_month'}
    assert normalize_monthly_volume(value)==value


def test_model_monthly_proposal_requires_its_own_quantity_period_and_unit():
    enquiry={'query':'15–20 outlets and 20,000 requests per month.'}
    state=build_diagnostic_state(enquiry)
    plan=QualificationPlan.model_validate({'reason':'Inspect the count binding.','supplied_facts':[
        {'field':'monthly_volume','value':'15–20 outlets','evidence':enquiry['query']}]})
    merge_model_facts(state,plan,enquiry)
    assert 'monthly_volume' not in state.facts
    plan=QualificationPlan.model_validate({'reason':'Use the explicit API workload.','supplied_facts':[
        {'field':'monthly_volume','value':20000,'evidence':'20,000 requests per month'}]})
    merge_model_facts(state,plan,enquiry)
    assert state.facts['monthly_volume'].value=={'raw':'20,000 requests per month','requests_per_month':20000,'unit':'requests_per_month'}


def test_matrix_monthly_context_recovers_operations_without_multiplying_pairs():
    enquiry={'query':'Ola Maps Distance Matrix: send 10 origins x 5 destinations about 2,000 times a month.'}
    partial={'raw':'2,000','requests_per_month':2000,'unit':'per_month'}
    state=build_diagnostic_state(enquiry)
    context=context_from_result(result_for(enquiry,partial),state,enquiry)
    value=context.facts['monthly_volume'].value
    assert value['requests_per_month']==2000
    assert value['unit']=='matrices_per_month'
    assert normalize_monthly_volume(value)==value
