"""The dashboard discovers new runs and displays the entire metric contract."""
import json
from streamlit.testing.v1 import AppTest
from copilot.evaluation.artifacts import publish
from copilot.evaluation.contracts import METRICS


def fixture(folder,identifier,bucket):
    folder.mkdir()
    records=[{'record_id':identifier,'arm':arm,'bucket':bucket,'api':'directions','team':'Support',
              'metrics':{k:(.5 if k=='answer_accuracy' else None) for k in METRICS}} for arm in ('baseline','agent')]
    publish(folder,{'split':'synthetic','binding':{'strategy':'zero_shot','retrieval':'fixture'}},records)
    (folder/'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))


def test_refresh_and_filters_require_no_artifact_edits(tmp_path):
    fixture(tmp_path/'first','SYN-1','docs')
    script=tmp_path/'ui.py'
    script.write_text('from copilot.metrics_dashboard.viewer import render\n'+f'render({str(tmp_path)!r})\n')
    app=AppTest.from_file(str(script),default_timeout=15).run()
    assert not app.exception
    assert len(app.selectbox(key='eval_run').options)==1
    assert len(app.selectbox(key='eval_metric').options)==len(METRICS)
    fixture(tmp_path/'second','SYN-2','qualification')
    app.run()
    assert len(app.selectbox(key='eval_run').options)==2
    app.selectbox(key='eval_run').set_value(str(tmp_path/'second')).run()
    assert 'qualification' in app.selectbox(key='eval_bucket').options
    assert not app.exception
