"""Exercise 20 synthetic review decisions through the real Streamlit review panel."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, create_autospec
from datetime import datetime, timezone
import json,sys

from streamlit.testing.v1 import AppTest
from copilot.case_storage import cases, sandbox, handlers
from copilot.case_storage.db import connect
from copilot.enquiry_workflow.cases import run_case
from copilot.model_gateway.client import LLMClient
from tests.support.helpers import completion, model_json

OUT=Path(sys.argv[1])
OUT.mkdir(parents=True,exist_ok=True)
app_path=Path.cwd()/'copilot/streamlit_ui/streamlit_app.py'
client=create_autospec(LLMClient,instance=True)
def reply(messages, **options):
    incident="503" in messages[-1]["content"]
    return completion(model_json(
        intent="troubleshooting" if incident else "docs_how_to",
        sub_intent="production_incident" if incident else "parameter_question",
        api="directions",team="Support"))
client.complete.side_effect=reply

def widget(items,label):
    return next(item for item in items if item.label==label)

with TemporaryDirectory(prefix="activity17-review-") as temp:
    db=Path(temp)/'review.db'
    reviewer="acceptance_test_reviewer"
    records=[]
    with patch('copilot.case_storage.db.DB_PATH',db), \
         patch.object(cases,'_approvers_cfg',return_value={'approvers':[{'name':reviewer,'can_approve':'all'}]}), \
         patch('copilot.enquiry_workflow.cases.run_case',
               side_effect=lambda *args,**kwargs:run_case(*args,client=client,diagnostic_planning=False,**kwargs)), \
         patch('copilot.enquiry_workflow.cases.add_follow_up_questions',side_effect=lambda result,*args,**kwargs:result):
        app=AppTest.from_file(str(app_path),default_timeout=20).run()
        assert not app.exception
        for kind in ('record_update','escalation'):
            for index in range(10):
                action_number=len(records)+1
                decision=('approve','edit','reject')[index%3]
                app.selectbox(key='selected_case').select_index(0).run()
                if kind=='record_update':
                    record_id=('TKT-' if index%2==0 else 'OPP-')+str(17000+index)
                    field='status' if record_id.startswith('TKT-') else 'stage'
                    query=f"Update sandbox record {record_id}, {field} to triaged."
                else:
                    record_id=None
                    query=f"Production is down. Directions returns 503 for all requests. Incident {index+1}."
                widget(app.text_area,'Customer enquiry').set_value(query)
                widget(app.button,'Run enquiry').click().run()
                assert not app.exception, str(app.exception)
                case_id=app.selectbox(key='selected_case').value
                with closing(connect(db)) as con:
                    pending=cases.list_pending(con,case_id)
                    assert len(pending)==1 and pending[0]['type']==kind
                    action=pending[0]
                    aid=action['id']
                    assert action['status']=='pending' and action['applied_at'] is None
                    before=cases.get_case(con,case_id)
                    record_before=sandbox.get(con,record_id) if record_id else None
                    assert before['status']=='awaiting_approval'
                    if record_id:assert record_before=={}
                    # Direct execution before approval must be rejected.
                    invoked=[]
                    try:cases.apply_approved(con,aid,lambda payload:invoked.append(payload))
                    except ValueError:pass
                    else:raise AssertionError('A pending action was applied.')
                    assert not invoked
                    unauthorized_blocked=False
                    try:handlers.approve_and_apply(con,aid,approver='unlisted_test_actor')
                    except ValueError:unauthorized_blocked=True
                    assert unauthorized_blocked and cases.get_action(con,aid)['status']=='pending'
                assert widget(app.selectbox,'Pending proposal')
                widget(app.selectbox,'Reviewer').set_value(reviewer)
                edit_value=None
                if decision=='edit':
                    if record_id:
                        edit_value={field:'reviewer_edited'}
                        widget(app.text_area,'Proposed fields').set_value(json.dumps(edit_value))
                    else:
                        edit_value='Reviewer clarified the incident scope before handoff.'
                        widget(app.text_area,'Handoff summary').set_value(edit_value)
                widget(app.text_input,'Decision note').set_value(f"Acceptance scenario {action_number}: {decision}")
                widget(app.button,'Reject' if decision=='reject' else 'Approve').click().run()
                assert not app.exception, str(app.exception)
                with closing(connect(db)) as con:
                    final_action=cases.get_action(con,aid)
                    audit=next(d for d in cases.decision_log(con) if d['action_id']==aid)
                    after=cases.get_case(con,case_id)
                    record_after=sandbox.get(con,record_id) if record_id else None
                    assert audit['reviewer']==reviewer and audit['decided_at']
                    datetime.fromisoformat(audit['decided_at'])
                    assert audit['decision']==('rejected' if decision=='reject' else 'approved')
                    assert isinstance(audit['final_diff'],dict)
                    assert not cases.list_pending(con,case_id)
                    if decision=='reject':
                        assert audit['final_diff']=={} and final_action['applied_at'] is None
                        if record_id:assert record_after==record_before
                        else:assert after['owner']==before['owner'] and after['next_action']==before['next_action']
                    else:
                        assert final_action['applied_at'] and audit['final_diff']
                        if record_id:
                            expected_value='reviewer_edited' if decision=='edit' else 'triaged'
                            assert record_after[field]==expected_value
                            assert audit['final_diff']=={field:{'old':None,'new':expected_value}}
                            assert audit['final']==final_action['edited_payload'] or audit['final']==final_action['payload']
                        else:
                            application_before={**before,'status':'approved_pending_apply'}
                            expected={f:{'old':application_before[f],'new':after[f]} for f in ('status','owner','next_action') if application_before[f]!=after[f]}
                            assert audit['final_diff']==expected
                            assert after['status']=='escalated'
                            if decision=='edit':assert audit['final']['summary']==edit_value
                        try:cases.apply_approved(con,aid,lambda payload:(_ for _ in ()).throw(AssertionError('duplicate effect')))
                        except ValueError:pass
                        else:raise AssertionError('A decided action was applied twice.')
                    records.append({'scenario':action_number,'action_type':kind,'decision':decision,
                                    'held_for_review':True,'unauthorized_approval_blocked':unauthorized_blocked,
                                    'effect_verified':True,'audit':audit})
                print(f"{action_number}/20 {kind} {decision}",flush=True)
        # Reopen the UI and database and verify every decision survives.
        app=AppTest.from_file(str(app_path),default_timeout=20).run()
        assert not app.exception
        with closing(connect(db)) as con:
            audits=cases.decision_log(con)
            assert len(audits)==20
            assert {d['action_id'] for d in audits}=={r['audit']['action_id'] for r in records}
            assert not cases.list_pending(con)
        assert app.json
    # Export audit evidence from the isolated DB before temporary cleanup.
    from collections import Counter
    summary={'scenario_count':20,'held_for_review':sum(r['held_for_review'] for r in records),
             'complete_audit_records':sum(bool(r['audit']['reviewer'] and r['audit']['decided_at'] and r['audit']['decision'])
                                          and isinstance(r['audit']['final_diff'],dict) for r in records),
             'decisions':dict(Counter(r['decision'] for r in records)),
             'action_types':dict(Counter(r['action_type'] for r in records)),
             'unauthorized_approval_blocked':sum(r['unauthorized_approval_blocked'] for r in records),
             'reviewer':'synthetic authorized acceptance reviewer in isolated configuration',
             'scope':'Real workflow proposals and Streamlit review UI. Scripted model responses, controlled follow-up selector, diagnostic planning disabled.',
             'passed':True}
    (OUT/'per-action.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
    (OUT/'scores.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
