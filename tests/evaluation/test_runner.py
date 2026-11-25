"""Exercise binding, failure accounting and resume without endpoint requests."""
import json
from types import SimpleNamespace
from pathlib import Path
import pytest
from copilot.evaluation import runner
from copilot.evaluation.contracts import Prediction,Judgement
from copilot.evaluation.data import read_cases,sample


def prediction():
    return Prediction(answer='A supported response.',citations=[],clarifying_questions=[],qualification={},comparison={},
                      owner='Support L1',next_action='answer_directly',should_escalate=False,record_update=None,
                      intent='docs_how_to',api='directions',team='Support')


def test_resuming_does_not_repeat_generation_and_changed_input_is_rejected(tmp_path,monkeypatch):
    case=sample(read_cases())[0]
    calls=[]
    def baseline(context,strategy,client):
        assert set(context)=={'query','history','known_facts'}
        calls.append(context)
        return prediction()
    monkeypatch.setattr(runner.baselines,'run',baseline)
    monkeypatch.setattr(runner.judge,'evaluate',lambda *a:Judgement(answer_accuracy=.5,grounding=1,
        comparison_completeness=.5,qualification_completeness=.5,history_use=1,citation_supported=[],reasons={}))
    folder=tmp_path/'run'
    first=runner.run(folder,[case],mode='bm25',arms=('baseline',),client=SimpleNamespace(_model='test'))
    second=runner.run(folder,[case],mode='bm25',arms=('baseline',),client=SimpleNamespace(_model='test'))
    assert len(calls)==1 and first['metrics_sha256']==second['metrics_sha256']
    assert first['paired_cases']==0 and first['cases']==1
    changed={**case,'input':{**case['input'],'query':'Changed query'}}
    with pytest.raises(ValueError,match='changed'):
        runner.run(folder,[changed],mode='bm25',arms=('baseline',),client=SimpleNamespace(_model='test'))


def test_failed_generation_is_counted_and_never_silently_dropped(tmp_path,monkeypatch):
    case=sample(read_cases())[0]
    def fail(*a):
        raise ValueError('Do not persist private endpoint details')
    monkeypatch.setattr(runner.baselines,'run',fail)
    summary=runner.run(tmp_path/'run',[case],mode='bm25',arms=('baseline',),client=SimpleNamespace(_model='test'))
    assert summary['errors']==1 and summary['records']==1
    rows=(tmp_path/'run/records.jsonl').read_text()
    assert 'private endpoint details' not in rows
    row=json.loads(rows)
    assert row['metrics']['answer_accuracy']==0 and row['metrics']['schema_validity']==0


def test_uncertain_interrupted_generation_cannot_be_replayed(tmp_path,monkeypatch):
    case=sample(read_cases())[0]
    monkeypatch.setattr(runner.baselines,'run',lambda *a:prediction())
    monkeypatch.setattr(runner.judge,'evaluate',lambda *a:Judgement(answer_accuracy=1,grounding=1,
        comparison_completeness=1,qualification_completeness=1,history_use=1,citation_supported=[],reasons={}))
    folder=tmp_path/'run'
    runner.run(folder,[case],mode='bm25',arms=('baseline',),client=SimpleNamespace(_model='test'))
    (folder/'generations.jsonl').write_text('')
    (folder/'inflight.json').write_text(json.dumps({'record_id':case['record_id'],'arm':'baseline'}))
    with pytest.raises(ValueError,match='ambiguous'):
        runner.run(folder,[case],mode='bm25',arms=('baseline',),client=SimpleNamespace(_model='test'))
