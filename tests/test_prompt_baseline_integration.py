"""The isolated baseline must use the shared model client without invoking tools."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


def load_baseline(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'prompt-engineering-baseline'))
    return importlib.import_module('app.llm'), importlib.import_module('app.baseline.prompting')


def test_all_three_strategies_use_the_shared_gateway(monkeypatch):
    adapter, baseline = load_baseline(monkeypatch)
    answer = json.dumps({'intent':'error_diagnosis','summary':'Inspect the reported failure.',
                         'missing_info':['redacted_request'],'recommended_action':'Inspect a redacted request.','confidence':0.8})
    client = Mock()
    client.complete.return_value = SimpleNamespace(text=answer, usage={'total_tokens':20},
        finish_reason='stop',model='Qwen/Qwen3-8B',latency_ms=10)
    monkeypatch.setattr(adapter,'LLMClient',lambda:client)
    result = baseline.run_baseline('Directions returns an error. What should we inspect?', 'support')
    assert {row['strategy'] for row in result['strategies']} == {
        'few_shot_structured','chain_of_thought','decomposition'}
    assert all(row['failure'] is None for row in result['strategies'])
    assert client.complete.call_count == 10
    for call in client.complete.call_args_list:
        assert all(item['role'] in {'system','user'} for item in call.args[0])
        assert call.kwargs['temperature'] in {0,0.6}
        assert 'tools' not in call.kwargs


def test_gateway_preserves_roles_generation_settings_and_metadata(monkeypatch):
    adapter, _ = load_baseline(monkeypatch)
    from langchain_core.messages import HumanMessage, SystemMessage
    client = Mock()
    client.complete.return_value = SimpleNamespace(text='ok',usage={'total_tokens':12},
        finish_reason='stop',model='Qwen/Qwen3-8B',latency_ms=8)
    monkeypatch.setattr(adapter,'LLMClient',lambda:client)
    result = adapter.get_llm(0.6).invoke([SystemMessage(content='Be concise.'),HumanMessage(content='Hello')],max_tokens=64)
    client.complete.assert_called_once_with([{'role':'system','content':'Be concise.'},
        {'role':'user','content':'Hello'}],temperature=0.6,max_tokens=64)
    assert result.content == 'ok'
    assert result.response_metadata['token_usage']['total_tokens'] == 12
