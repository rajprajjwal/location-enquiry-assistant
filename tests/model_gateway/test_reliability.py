"""Reliability boundaries that must hold across calls and graph steps."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import time
from types import SimpleNamespace
from threading import Event

import pytest
from pydantic import ValidationError

from copilot.enquiry_workflow.verification.reliability_faults import Clock, FaultClient, MODES, run_scenario
from copilot.model_gateway.client import BudgetExceeded, ConfigError, LLMError
from copilot.model_gateway.reliability import (
    DeadlineExceeded, Limits, QueryBudgetExceeded, RetryLimitExceeded, ToolTimeout,
    active_query, bounded_tool, query_session, step_scope,
)
from copilot.model_gateway.token_counting import count_metadata, count_prompt, _resources
from copilot.registered_tools.tool_registry import DocumentSearchTool, ToolRegistry


@pytest.mark.parametrize("mode", MODES)
def test_faults_recover_or_return_the_expected_safe_fallback(mode, tmp_path):
    for variation in range(5):
        row = run_scenario(mode, variation, tmp_path)
        assert row["passed"], row


def test_limits_reject_extra_fields_and_more_than_two_retries():
    with pytest.raises(ValidationError):
        Limits(max_retries_per_step=3)
    with pytest.raises(ValidationError):
        Limits(unlimited=True)
    with pytest.raises(ValidationError):
        Limits(enquiry_timeout_seconds=float("inf"))


def test_zero_retry_configuration_does_not_wait_or_repeat():
    clock = Clock()
    client = FaultClient("persistent_model_timeout", clock)
    with query_session(Limits(max_retries_per_step=0), clock=clock, sleeper=clock.advance) as session:
        with pytest.raises(LLMError):
            client.complete([{"role": "user", "content": "Reply."}], max_tokens=128)
        assert client.calls == 1
        assert session.retries == {}
        assert clock.now == 0


def test_nested_calls_share_cumulative_reservations():
    clock = Clock()
    client = FaultClient("healthy", clock)
    messages = [{"role": "user", "content": "Reply with JSON."}]
    one_call = count_prompt(messages) + count_metadata(messages, {}) + 64 + 128
    with query_session(Limits(token_budget=one_call), clock=clock) as session:
        client.complete(messages, max_tokens=128)
        with pytest.raises(BudgetExceeded):
            client.complete(messages, max_tokens=128)
        assert session.reserved_tokens == one_call
        assert session.model_attempts == client.calls == 1
    assert active_query() is None


def test_json_repair_and_transport_retries_share_the_step_limit():
    clock = Clock()
    client = FaultClient("healthy", clock)
    original = client._once
    count = 0
    def once(*args):
        nonlocal count
        count += 1
        if count <= 2:
            raise TimeoutError()
        return original(*args)
    client._once = once
    with query_session(clock=clock, sleeper=clock.advance) as session:
        with step_scope("interpretation"):
            client.complete([{"role": "user", "content": "Reply."}], max_tokens=128)
            with pytest.raises(RetryLimitExceeded):
                session.retry()
        assert session.retries == {"interpretation": 2}
        assert count == 3


def test_http_authentication_failure_is_not_retried():
    clock = Clock()
    client = FaultClient("healthy", clock)
    calls = []
    class AuthenticationFailure(Exception):
        status_code = 401
    def once(*args):
        calls.append(1)
        raise AuthenticationFailure("synthetic-key")
    client._once = once
    with query_session(clock=clock, sleeper=clock.advance) as session:
        with pytest.raises(LLMError) as error:
            client.complete([{"role": "user", "content": "Reply."}], max_tokens=128)
        assert len(calls) == 1
        assert session.retries == {}
        assert "synthetic-key" not in str(error.value)


def test_expired_deadline_stops_before_transport_and_rejects_long_backoff():
    clock = Clock()
    client = FaultClient("healthy", clock)
    with query_session(Limits(enquiry_timeout_seconds=1), clock=clock) as session:
        with pytest.raises(DeadlineExceeded):
            session.pause(2)
        clock.advance(2)
        with pytest.raises(BudgetExceeded):
            client.complete([{"role": "user", "content": "Reply."}], max_tokens=128)
        assert client.calls == 0


def test_late_tool_result_is_discarded_and_context_resets():
    with query_session(Limits(tool_timeout_seconds=.01)):
        def slow(_):
            time.sleep(.05)
            return {"results": []}
        with pytest.raises(ToolTimeout):
            bounded_tool(slow, {})
    assert active_query() is None
    time.sleep(.06)


def test_tool_retry_requires_explicit_safe_registration():
    tool = DocumentSearchTool().tool_definition()
    calls = []
    def fail(_):
        calls.append(1)
        raise RuntimeError("Injected failure")
    registry = ToolRegistry()
    registry.register(replace(tool, executor=fail, retry_safe=False))
    with query_session() as session:
        with pytest.raises(RuntimeError):
            registry.execute("document_search", {"query": "waypoints"})
        assert len(calls) == 1
        assert session.retries == {}


def test_invalid_tool_inputs_and_results_do_not_retry():
    registry = ToolRegistry()
    registry.register(replace(DocumentSearchTool().tool_definition(), executor=lambda _: {"results": "bad"}))
    with query_session() as session:
        with pytest.raises(KeyError):
            registry.execute("unknown", {})
        with pytest.raises(ValueError, match="Input validation"):
            registry.execute("document_search", {"query": 4})
        with pytest.raises(ValueError, match="Output validation"):
            registry.execute("document_search", {"query": "waypoints"})
        assert session.retries == {}
        assert [row["execution_status"] for row in registry.execution_log] == ["rejected", "rejected", "error"]


def test_tokenizer_configuration_failure_is_reported_without_network(monkeypatch, tmp_path):
    _resources.cache_clear()
    monkeypatch.setenv("TRACKB_TOKENIZER_DIR", str(tmp_path))
    client = FaultClient("healthy", Clock())
    try:
        with pytest.raises(ConfigError):
            client.complete([{"role": "user", "content": "Reply."}], max_tokens=128)
        assert client.calls == 0
    finally:
        _resources.cache_clear()


def test_concurrent_enquiries_have_independent_budgets_and_thread_contexts():
    def run(tokens):
        with query_session(Limits(token_budget=100)) as session:
            session.reserve(tokens)
            with pytest.raises(QueryBudgetExceeded):
                session.reserve(101)
            return bounded_tool(lambda _: active_query().reserved_tokens, {})
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(run, [20, 30])) == [20, 30]
    assert active_query() is None


def test_model_lock_wait_obeys_the_enquiry_deadline():
    from copilot.model_gateway.client import _CALL_LOCK
    client = FaultClient("healthy", Clock())
    _CALL_LOCK.acquire()
    try:
        with query_session(Limits(enquiry_timeout_seconds=.01)) as session:
            with pytest.raises(BudgetExceeded, match="waiting for the model"):
                client.complete([{"role": "user", "content": "Reply."}], max_tokens=128)
            assert client.calls == 0
            assert session.events[-1]["kind"] == "query_timeout"
    finally:
        _CALL_LOCK.release()


def test_http_timeout_uses_remaining_deadline_and_disables_sdk_retries(monkeypatch):
    import openai
    from copilot.model_gateway.client import LLMClient
    observed = {}
    def http_client(**options):
        observed.update(options)
        return SimpleNamespace(close=lambda: None)
    def sdk(**options):
        observed["sdk_max_retries"] = options["max_retries"]
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=lambda **_: SimpleNamespace(choices=[], model="synthetic", usage=None))))
    monkeypatch.setattr("ssl.create_default_context", lambda **_: object())
    monkeypatch.setattr("httpx.Client", http_client)
    monkeypatch.setattr("openai.OpenAI", sdk)
    client = LLMClient(api_key="synthetic", ca_cert=__file__)
    clock = Clock()
    with query_session(Limits(enquiry_timeout_seconds=8, model_timeout_seconds=3), clock=clock):
        clock.advance(7)
        client.complete([{"role": "user", "content": "Reply."}], max_tokens=128)
    assert observed["timeout"] == 1
    assert observed["sdk_max_retries"] == 0


def test_timed_out_worker_cannot_start_another_model_request():
    release, finished = Event(), Event()
    client = FaultClient("healthy", Clock())
    rejected = []
    def slow(_):
        release.wait(1)
        try:
            client.complete([{"role": "user", "content": "Reply."}], max_tokens=128)
        except BudgetExceeded:
            rejected.append(True)
        finally:
            finished.set()
        return {}
    with query_session(Limits(tool_timeout_seconds=.01)):
        with pytest.raises(ToolTimeout):
            bounded_tool(slow, {})
        release.set()
        assert finished.wait(1)
    assert rejected == [True]
    assert client.calls == 0


def test_nested_embedding_retries_share_the_tool_retry_limit(monkeypatch):
    from copilot.rag.document_indexing import embed
    calls = []
    def post(*args, **options):
        calls.append(options)
        return SimpleNamespace(status_code=503)
    monkeypatch.setattr(embed, "_http", lambda: SimpleNamespace(post=post))
    registry = ToolRegistry()
    registry.register(DocumentSearchTool(search_function=lambda _: embed._post_batch(["query"])).tool_definition())
    clock = Clock()
    with query_session(clock=clock, sleeper=clock.advance) as session:
        with pytest.raises(RuntimeError):
            registry.execute("document_search", {"query": "waypoints"})
        assert len(calls) == 3
        assert session.retries == {"enquiry": 2}
        assert all(0 < row["timeout"] <= 15 for row in calls)
