"""Exercise status capture, history, reopening, isolation and source deletion."""
from contextlib import closing

import pytest

from copilot.case_storage import cases
from copilot.case_storage.db import connect
from copilot.enquiry_workflow import cases as service
from copilot.enquiry_workflow.case_memory import load_conversation
from copilot.enquiry_workflow.deletion import delete_enquiry
from copilot.registered_tools.tool_registry import DocumentSearchTool
from tests.enquiry_workflow.test_escalation import parsed_for

QUERY = 'How do I set waypoints in Mapbox Directions?'


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(service, 'interpret', lambda *a, **kw: parsed_for(QUERY, 'docs_how_to'))
    monkeypatch.setattr(service, 'add_follow_up_questions', lambda r, *a, **kw: r)
    return DocumentSearchTool(documents=[])


def submit(con, search, query=QUERY, **kwargs):
    return service.run_case(con, query, search=search, diagnostic_planning=False, **kwargs)


def test_staff_confirmation_survives_reopen_and_is_isolated(tmp_path, configured):
    path=tmp_path/'cases.db'
    with closing(connect(path)) as con:
        first=submit(con,configured,confirmed_customer_status='new')
        assert first['ownership_review']['customer_status']=='new'
        assert first['outputs']['responsible_role']['owner']=='Account team (Sales)'
    with closing(connect(path)) as con:
        again=submit(con,configured,case_id=first['case_id'])
        assert again['ownership_review']['customer_status']=='new'
        assert not again['ownership_review']['provisional']
        other=submit(con,configured)
        assert other['ownership_review']['customer_status']=='unknown'
        assert other['ownership_review']['provisional']
        assert other['case_id']!=first['case_id']


def test_correction_and_source_deletion_restore_previous_status(tmp_path, configured):
    with closing(connect(tmp_path/'cases.db')) as con:
        first=submit(con,configured,confirmed_customer_status='new')
        corrected=submit(con,configured,case_id=first['case_id'],confirmed_customer_status='existing')
        assert corrected['ownership_review']['customer_status']=='existing'
        later=submit(con,configured,case_id=first['case_id'])
        assert later['ownership_review']['customer_status']=='existing'
        delete_enquiry(con,corrected['trace_id'])
        state=load_conversation(con,first['case_id'])
        assert state.ownership_status['customer_status']=='new'
        restored=submit(con,configured,case_id=first['case_id'])
        assert restored['ownership_review']['customer_status']=='new'


def test_deleting_only_confirmation_leaves_later_turn_unconfirmed(tmp_path,configured):
    with closing(connect(tmp_path/'cases.db')) as con:
        first=submit(con,configured,confirmed_customer_status='existing')
        submit(con,configured,case_id=first['case_id'])
        delete_enquiry(con,first['trace_id'])
        assert load_conversation(con,first['case_id']).ownership_status=={}
        later=submit(con,configured,case_id=first['case_id'])
        assert later['ownership_review']['customer_status']=='unknown'


def test_saved_clarification_allows_short_customer_status_reply(tmp_path,configured):
    with closing(connect(tmp_path/'cases.db')) as con:
        cid=cases.create_case(con)
        cases.add_message(con,cid,'user',QUERY)
        cases.add_message(con,cid,'clarification','Are you a new or existing customer?')
        reply=submit(con,configured,'new',case_id=cid)
        assert reply['ownership_review']['customer_status']=='new'
        assert reply['outputs']['responsible_role']['owner']=='Account team (Sales)'
        assert load_conversation(con,cid).ownership_status['source']=='customer_message'


def test_deferring_status_does_not_repeat_the_question_after_reopen(tmp_path,configured):
    path=tmp_path/'cases.db'
    with closing(connect(path)) as con:
        cid=cases.create_case(con)
        cases.add_message(con,cid,'clarification','Are you a new or existing customer?')
        reply=submit(con,configured,"Let's leave that open for now.",case_id=cid)
        assert reply['ownership_review']['status_deferred']
    with closing(connect(path)) as con:
        again=submit(con,configured,case_id=cid)
        assert again['ownership_review']['status_deferred']
        assert again['ownership_review']['suggested_question'] is None


def test_account_record_status_is_used_when_no_turn_confirms_it(tmp_path,configured):
    with closing(connect(tmp_path/'cases.db')) as con:
        cid=cases.create_case(con)
        cases.set_fact(con,cid,'customer_status','existing')
        result=submit(con,configured,case_id=cid)
        assert result['ownership_review']['customer_status']=='existing'
        assert not result['ownership_review']['provisional']


def test_invalid_staff_status_does_not_create_a_case(tmp_path,configured):
    with closing(connect(tmp_path/'cases.db')) as con:
        with pytest.raises(ValueError,match='Confirmed customer status'):
            submit(con,configured,confirmed_customer_status='probably existing')
        assert cases.list_cases(con)==[]


def test_ui_confirmation_reaches_saved_case_routing(tmp_path,configured,monkeypatch):
    from pathlib import Path
    testing=pytest.importorskip('streamlit.testing.v1')
    path=tmp_path/'ui.db'
    monkeypatch.setattr('copilot.case_storage.db.DB_PATH',path)
    actual_run=service.run_case
    def run(*args,**kwargs):
        kwargs.update(search=configured,diagnostic_planning=False)
        return actual_run(*args,**kwargs)
    monkeypatch.setattr(service,'run_case',run)
    ui=Path(__file__).resolve().parents[2]/'copilot/streamlit_ui/streamlit_app.py'
    app=testing.AppTest.from_file(str(ui)).run()
    assert not app.exception
    relationship=next(control for control in app.selectbox if control.label=='Confirmed customer relationship')
    relationship.set_value('new')
    app.text_input[0].set_value('Status UI test')
    app.text_area[0].set_value(QUERY)
    next(button for button in app.button if button.label=='Run enquiry').click().run()
    assert not app.exception
    case_id=app.selectbox(key='selected_case').value
    assert case_id
    with closing(connect(path)) as con:
        saved=cases.load_state(con,case_id)['last_result']
        assert saved['ownership_review']['customer_status']=='new'
        assert saved['outputs']['responsible_role']['owner']=='Account team (Sales)'
    reopened=testing.AppTest.from_file(str(ui)).run()
    reopened.selectbox(key='selected_case').set_value(case_id).run()
    assert not reopened.exception
    assert reopened.text_area[0].value==''
