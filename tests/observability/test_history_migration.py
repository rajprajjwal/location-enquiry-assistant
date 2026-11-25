"""History verification reads existing trace IDs and detects changed reports."""
import json
from pathlib import Path
import pytest
from copilot.observability.verification import verify_history as history


def test_history_snapshot_and_comparison_are_read_only(tmp_path,monkeypatch):
    root=tmp_path/'evaluation'
    for name in ('frozen-paired','holdout-final'):
        folder=root/name;folder.mkdir(parents=True)
        for file in ('summary.json','records.jsonl','cases.jsonl'):
            (folder/file).write_text('{}\n')
        (folder/'manifest.json').write_text('{"started_at":"2026-11-25T00:00:00+00:00"}')
        (folder/'generations.jsonl').write_text(''.join(json.dumps({'trace_id':name+'-'+str(i)})+'\n' for i in range(2)))
    calls=[]
    class Client:
        def __init__(self,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def get(self,url,params):
            calls.append((url,params))
            class Response:
                def raise_for_status(self): pass
                def json(self): return {'data':[{'id':params['traceId']+'-observation'}],'meta':{}}
            return Response()
    monkeypatch.setattr(history.httpx,'Client',Client)
    monkeypatch.setattr(history,'load_environment',lambda _:dict(LANGFUSE_BASE_URL='http://localhost:3000',LANGFUSE_PUBLIC_KEY='fixture',LANGFUSE_SECRET_KEY='fixture'))
    source=tmp_path/'source.json'
    history.verify('unused',root,source)
    copied=tmp_path/'copied.json'
    report=history.verify('unused',root,copied,source)
    assert report['passed'] and len(report['observations'])==4
    assert report['new_traces_created']==report['model_calls']==0
    assert len(calls)==8 and all(url=='/api/public/v2/observations' for url,_ in calls)
    (root/'holdout-final/summary.json').write_text('{"changed":true}')
    with pytest.raises(ValueError,match='report_sha256'):
        history.verify('unused',root,tmp_path/'failed.json',source)
    assert not (tmp_path/'failed.json').exists()
