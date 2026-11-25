"""Saved report browsing cannot escape report roots or start inference."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from copilot.metrics_dashboard.reports import available_reports,read_report
from copilot.metrics_dashboard.stage_reports import stage


def test_report_roots_exclude_runtime_files_and_symlink_escape(tmp_path):
    root=tmp_path/'results'
    root.mkdir()
    report=root/'report.md';report.write_text('# Saved result')
    private=tmp_path/'private.env';private.write_text('private fixture')
    (root/'escape.md').symlink_to(private)
    (root/'state.db').write_bytes(b'database')
    (root/'large.txt').write_bytes(b'x'*(5*1024*1024+1))
    nested=root/'old/runtime';nested.mkdir(parents=True)
    (nested/'private.json').write_text('{}')
    runtime=tmp_path/'copilot/observability/runtime';runtime.mkdir(parents=True)
    (runtime/'secret.json').write_text('{}')
    assert available_reports(tmp_path)==[report]
    with pytest.raises(ValueError): read_report(tmp_path,private)


def test_bundle_preserves_report_bytes_without_inputs_or_runtime_state(tmp_path):
    import hashlib
    repo=tmp_path/'repo';root=repo/'results/evaluation/frozen-paired';root.mkdir(parents=True)
    (root/'records.jsonl').write_text('{"saved_score":0.5}\n')
    (root/'summary.json').write_text('{"saved":true}')
    (root/'cases.jsonl').write_text('{"gold":"excluded"}\n')
    nested=root/'runtime';nested.mkdir()
    (nested/'secret.json').write_text('{"private":true}')
    out=tmp_path/'bundle'
    result=stage(repo,out)
    assert len(result['sha256'])==2 and result['inference_calls']==0
    for name,expected in result['sha256'].items():
        assert (out/name).read_bytes()==(repo/name).read_bytes()
        assert hashlib.sha256((out/name).read_bytes()).hexdigest()==expected
    assert not (out/'results/evaluation/frozen-paired/cases.jsonl').exists()
    assert not (out/'results/evaluation/frozen-paired/runtime').exists()
    (root/'summary.json').unlink()
    stage(repo,out)
    assert not (out/'results/evaluation/frozen-paired/summary.json').exists()
    unrelated=tmp_path/'unrelated';unrelated.mkdir();(unrelated/'keep.txt').write_text('keep')
    with pytest.raises(ValueError):stage(repo,unrelated)
    assert (unrelated/'keep.txt').read_text()=='keep'


def test_report_view_renders_and_searches_saved_activity_files(tmp_path):
    root=tmp_path/'results';root.mkdir()
    (root/'report.md').write_text('# Existing report\nNo regeneration needed.')
    component=tmp_path/'copilot/model_gateway/results';component.mkdir(parents=True)
    (component/'summary.json').write_text('{"passed":true}')
    script=tmp_path/'ui.py'
    script.write_text('from copilot.metrics_dashboard.reports import render\n'+f'render({str(tmp_path)!r})\n')
    app=AppTest.from_file(str(script)).run()
    assert not app.exception
    assert len(app.selectbox(key='saved_report_path').options)==2
    app.text_input(key='saved_report_search').set_value('model_gateway').run()
    assert not app.exception
    assert len(app.selectbox(key='saved_report_path').options)==1
