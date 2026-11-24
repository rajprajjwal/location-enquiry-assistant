from types import SimpleNamespace

import pytest

from copilot.model_gateway.client import (
    BudgetExceeded, Completion, ConfigError, DEFAULT_MODEL, LLMClient, MAX_CONTEXT_TOKENS,
)
from copilot.model_gateway.endpoint_checks import assert_probe, percentile, smoke


def client(tmp_path):
    cert = tmp_path / "ca.pem"
    cert.touch()
    return LLMClient(api_key="secret-test-key", ca_cert=str(cert))


def response(text=None):
    tool = SimpleNamespace(
        id="call-1", type="function",
        function=SimpleNamespace(name="echo_value", arguments='{"value":7}'),
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=text, tool_calls=[tool]), finish_reason="tool_calls",
        )],
        model=DEFAULT_MODEL, usage=None,
    )


def test_function_metadata_and_tool_response_survive(tmp_path, monkeypatch):
    endpoint = client(tmp_path)
    captured = []
    def once(messages, max_tokens, temperature, extra):
        captured.append((messages, extra))
        return response()
    monkeypatch.setattr(endpoint, "_once", once)
    messages = [
        {"role": "assistant", "content": None, "tool_calls": [{"id": "prior", "type": "function", "function": {"name": "echo_value", "arguments": "{}"}}]},
        {"role": "tool", "content": "7", "tool_call_id": "prior"},
    ]
    tools = [{"type": "function", "function": {"name": "echo_value"}}]
    completion = endpoint.complete(messages, tools=tools, tool_choice="required")
    assert captured[0][0] == messages
    assert captured[0][1]["tools"] == tools
    assert captured[0][1]["tool_choice"] == "required"
    assert completion.tool_calls[0]["function"]["arguments"] == '{"value":7}'
    assert completion.finish_reason == "tool_calls" and completion.text == ""
    assert messages[0]["content"] is None


def test_json_option_and_redaction(tmp_path, monkeypatch):
    endpoint = client(tmp_path)
    captured = []
    def once(messages, max_tokens, temperature, extra):
        captured.append(extra)
        result = response("secret-test-key")
        result.choices[0].message.tool_calls[0].function.arguments = '{"token":"secret-test-key"}'
        return result
    monkeypatch.setattr(endpoint, "_once", once)
    completion = endpoint.complete([{"role": "user", "content": "JSON"}],
                                   response_format={"type": "json_object"})
    assert captured[0]["response_format"] == {"type": "json_object"}
    assert "secret-test-key" not in repr(completion)


def test_tool_definitions_and_prior_calls_count_toward_context(tmp_path, monkeypatch):
    endpoint = client(tmp_path)
    monkeypatch.setattr(endpoint, "_once", lambda *args: pytest.fail("network call"))
    with pytest.raises(BudgetExceeded):
        endpoint.complete([{"role": "user", "content": "short"}], tools=[{"type": "function", "function": {"name": "large_tool", "description": " x" * MAX_CONTEXT_TOKENS}}])
    with pytest.raises(BudgetExceeded):
        endpoint.complete([{"role": "assistant", "content": None, "tool_calls": [{"id": "prior", "type": "function", "function": {"name": "large_tool", "arguments": " x" * MAX_CONTEXT_TOKENS}}]}])
    with pytest.raises(ConfigError, match="requires tools"):
        endpoint.complete([], tool_choice="auto")


def test_smoke_checks_actual_features_and_continues_after_a_failure():
    class Fake:
        def complete(self, messages, **options):
            if "tools" in options:
                return Completion("", "", DEFAULT_MODEL, None, 30, False, [{
                    "id": "c1", "type": "function",
                    "function": {"name": "echo_value", "arguments": '{"value":7}'},
                }], "tool_calls")
            text = '{"status":"ok"}' if "response_format" in options else "pong"
            return Completion(text, text, DEFAULT_MODEL, None, 10, False)
    assert all(item["passed"] for item in smoke(Fake()))
    bad = Completion('{"value":7}', "", DEFAULT_MODEL, None, 10, False)
    with pytest.raises(ValueError):
        assert_probe("tool", bad)
    bad.finish_reason = "length"
    with pytest.raises(ValueError, match="output limit"):
        assert_probe("chat", bad)
    assert percentile([30, 10, 20], 0.5) == 20
    assert percentile([30, 10, 20], 0.95) == 30
    assert percentile([], 0.95) is None


def test_frozen_input_integrity_checked_before_calls(tmp_path):
    import json
    from copilot.model_gateway.endpoint_checks import frozen
    (tmp_path / "inputs.jsonl").write_text('{"record_id":"changed"}\n')
    (tmp_path / "manifest.json").write_text(json.dumps({"inputs_sha256": "incorrect"}))
    class NeverCall:
        def complete(self, *args, **kwargs):
            pytest.fail("modified frozen data reached the endpoint")
    with pytest.raises(ValueError, match="hash differs"):
        frozen(NeverCall(), tmp_path)


def test_smoke_keeps_other_probe_results_after_endpoint_error():
    class Failing:
        count = 0
        def complete(self, *args, **kwargs):
            self.count += 1
            raise RuntimeError("synthetic unavailable")
    endpoint = Failing()
    results = smoke(endpoint)
    assert endpoint.count == 3
    assert [item["probe"] for item in results] == ["chat", "json", "tool"]
    assert all(not item["passed"] and item["error_type"] == "RuntimeError" for item in results)
