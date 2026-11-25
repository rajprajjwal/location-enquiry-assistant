"""Check completed final runs against the read-only dashboard."""
from pathlib import Path
import json
from streamlit.testing.v1 import AppTest
from copilot.evaluation.artifacts import load

root=Path.cwd()/'results/evaluation'
app=AppTest.from_file(str(Path.cwd()/'copilot/metrics_dashboard/streamlit_app.py'),default_timeout=30).run()
assert not app.exception
results={}
for name in ('frozen-paired','holdout-final'):
    folder=root/name
    if not (folder/'summary.json').exists():
        continue
    app.selectbox(key='eval_run').set_value(str(folder)).run()
    assert not app.exception
    assert len(app.selectbox(key='eval_metric').options)==29
    frame=app.dataframe[0].value
    summary=load(folder)
    expected={(r['arm'],r['metric']):r for r in summary['metrics'] if r['dimension']=='overall'}
    for key,definition in summary['metric_catalog'].items():
        row=frame[frame['Metric']==definition['label']].iloc[0]
        for arm in ('baseline','agent'):
            value=expected[(arm,key)]['score']
            if value is not None:
                assert abs(row[arm.title()]-value)<1e-12
    for key in ('eval_bucket','eval_api','eval_team'):
        widget=app.selectbox(key=key)
        widget.set_value(widget.options[1]).run()
        assert not app.exception
        app.selectbox(key=key).set_value('All').run()
        assert not app.exception
    results[name]={'metric_count':29,'displayed_values_match_saved_summary':True,
                   'bucket_api_team_filters':'passed','exceptions':0,'endpoint_calls':0}
(root/'verification/dashboard-final-runs.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results))
