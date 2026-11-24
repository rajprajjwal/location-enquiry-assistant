"""A live score must not inherit historical owner or handoff decisions."""
import json

from copilot.enquiry_workflow.verification import verify_ownership_live as verifier
from copilot.models import InterpretationOutput
from tests.enquiry_workflow.test_escalation import parsed_for


def write_inputs(tmp_path, rows):
    path=tmp_path/'inputs.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    return path


def record(key='case-one'):
    return {'record_id':key,'query':'We are a new customer. How do I set waypoints?', 'history':[],
            'expected':{'owner':'Support L1','escalate':False},
            'actual':{'owner':'Support L1','escalate':False,'reason':'Historical correct result'}}


def test_saved_correct_owner_cannot_inflate_a_fresh_result(tmp_path,monkeypatch):
    monkeypatch.delenv('TRACKB_GT_CSV',raising=False)
    seen=[]
    def fresh(enquiry,**kwargs):
        seen.append(enquiry)
        return parsed_for(enquiry['query'],'docs_how_to')
    monkeypatch.setattr(verifier,'interpret',fresh)
    summary=verifier.verify_live(write_inputs(tmp_path,[record()]),tmp_path/'results',client=object())
    assert summary['owner_correct']==0
    assert summary['owner_accuracy_all_cases']==0
    assert seen==[{'query':record()['query'],'history':[],'known_facts':[]}]
    actual=json.loads((tmp_path/'results/predictions.jsonl').read_text())['actual']
    assert actual['owner']=='Account team (Sales)'


def test_failed_interpretation_stays_in_the_denominator(tmp_path,monkeypatch):
    monkeypatch.delenv('TRACKB_GT_CSV',raising=False)
    good=parsed_for(record()['query'],'docs_how_to')
    payload=good.model_dump(mode='json');payload.update(abstain=True,abstain_reason='model_unavailable')
    bad=InterpretationOutput.model_validate(payload)
    values=iter([good,bad])
    monkeypatch.setattr(verifier,'interpret',lambda *a,**kw:next(values))
    rows=[record('one'),record('two')]
    for r in rows:r['expected']['owner']='Account team (Sales)'
    summary=verifier.verify_live(write_inputs(tmp_path,rows),tmp_path/'results',client=object())
    assert summary['cases']==2 and summary['valid_cases']==1
    assert summary['owner_accuracy_all_cases']==.5
    assert not summary['complete_valid_run'] and not summary['passes']
    assert summary['errors']==[{'record_id':'two','error':'interpretation:model_unavailable'}]


def test_completed_run_resumes_without_calling_the_model(tmp_path,monkeypatch):
    monkeypatch.delenv('TRACKB_GT_CSV',raising=False)
    monkeypatch.setattr(verifier,'interpret',lambda *a,**kw:parsed_for(record()['query'],'docs_how_to'))
    inputs=write_inputs(tmp_path,[record()])
    first=verifier.verify_live(inputs,tmp_path/'results',client=object())
    def unexpected(*args,**kwargs):raise AssertionError('Completed case was rerun')
    monkeypatch.setattr(verifier,'interpret',unexpected)
    assert verifier.verify_live(inputs,tmp_path/'results',client=object())==first



def test_semantic_abstention_keeps_the_production_provisional_owner(tmp_path,monkeypatch):
    monkeypatch.delenv('TRACKB_GT_CSV',raising=False)
    payload=parsed_for('Please help','docs_how_to').model_dump(mode='json')
    payload.update(intent=None,sub_intent=None,api=None,team=None,abstain=True,abstain_reason='no_rule_match')
    parsed=InterpretationOutput.model_validate(payload)
    monkeypatch.setattr(verifier,'interpret',lambda *a,**kw:parsed)
    row=record();row['query']='Please help'
    summary=verifier.verify_live(write_inputs(tmp_path,[row]),tmp_path/'results',client=object())
    assert summary['valid_cases']==1 and summary['owner_correct']==1
    assert summary['semantic_abstentions']==['case-one']
    result=json.loads((tmp_path/'results/predictions.jsonl').read_text())
    assert result['actual']['ownership_review']['provisional']
