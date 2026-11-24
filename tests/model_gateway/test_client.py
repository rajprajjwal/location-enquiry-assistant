"""Acceptance test 6, plus the 429/503 backoff from test 5."""

from __future__ import annotations

import json
import subprocess

import pytest

from copilot.model_gateway.token_counting import count_prompt, count_metadata

from copilot.model_gateway.client import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    MAX_CONTEXT_TOKENS,
    BudgetExceeded,
    ConfigError,
    LLMClient,
    LLMError,
    TokenLimitError,
    estimate_input_tokens,
)


@pytest.fixture()
def ca_cert(tmp_path):
    cert = tmp_path / "ca.pem"
    subprocess.check_call(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(tmp_path / "key.pem"),
            "-out",
            str(cert),
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=test",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return cert


def _status(code: int, text: str = ""):
    class Status(Exception):
        def __init__(self):
            super().__init__(text or f"http {code}")
            self.status_code = code

    return Status()


def _install_openai(monkeypatch, create, capture=None):
    class FakeCompletions:
        def create(self, **kwargs):
            return create(**kwargs)

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            if capture is not None:
                capture.append(kwargs)
            self.chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)


def _response(text="pong", usage=True):
    class Usage:
        prompt_tokens = 3
        completion_tokens = 1
        total_tokens = 4

    class Message:
        content = text

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]
        model = DEFAULT_MODEL

    response = Response()
    response.usage = Usage() if usage else None
    return response


def test_missing_base_url_raises_before_any_network_call(monkeypatch) -> None:
    called = {"n": 0}

    class Boom:
        def __init__(self, **kwargs):
            called["n"] += 1

    monkeypatch.setattr("openai.OpenAI", Boom)
    with pytest.raises(ConfigError, match="base_url"):
        LLMClient(base_url=None, api_key="trackb-test-key", ca_cert="/no/such/cert")
    assert called["n"] == 0


def test_openai_env_is_ignored(monkeypatch, ca_cert) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-env-key-should-not-be-used")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.example/v1")
    monkeypatch.delenv("TRACKB_API_KEY", raising=False)
    monkeypatch.delenv("TRACKB_CA_CERT", raising=False)
    with pytest.raises(ConfigError, match="TRACKB_API_KEY"):
        LLMClient(ca_cert=str(ca_cert))

    capture = []
    _install_openai(monkeypatch, lambda **kwargs: _response(), capture)
    client = LLMClient(api_key="trackb-test-key", ca_cert=str(ca_cert))
    result = client.complete([{"role": "user", "content": "hi"}], max_tokens=16)
    assert capture[0]["api_key"] == "trackb-test-key"
    assert capture[0]["base_url"] == DEFAULT_BASE_URL
    assert capture[0]["max_retries"] == 0
    assert "openai-env-key-should-not-be-used" not in repr(capture[0])
    assert result.model == DEFAULT_MODEL
    assert result.usage == {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}
    assert "trackb-test-key" not in repr(client)


def test_max_tokens_above_1024_is_rejected(ca_cert, monkeypatch) -> None:
    called = {"n": 0}

    class Boom:
        def __init__(self, **kwargs):
            called["n"] += 1

    monkeypatch.setattr("openai.OpenAI", Boom)
    client = LLMClient(api_key="trackb-test-key", ca_cert=str(ca_cert))
    with pytest.raises(TokenLimitError):
        client.complete([{"role": "user", "content": "hi"}], max_tokens=1025)
    assert called["n"] == 0


def test_context_budget_rejects_before_network(ca_cert, monkeypatch) -> None:
    called = {"n": 0}

    class Boom:
        def __init__(self, **kwargs):
            called["n"] += 1

    monkeypatch.setattr("openai.OpenAI", Boom)
    client = LLMClient(api_key="trackb-test-key", ca_cert=str(ca_cert))
    over = [{"role": "user", "content": " x" * MAX_CONTEXT_TOKENS}]
    assert count_prompt(over) + 512 > MAX_CONTEXT_TOKENS
    with pytest.raises(BudgetExceeded):
        client.complete(over, max_tokens=512)
    assert called["n"] == 0

    # Locate the exact boundary using the same native tokenizer, including overhead.
    low, high = 0, MAX_CONTEXT_TOKENS
    while low + 1 < high:
        middle = (low + high) // 2
        candidate = [{"role": "user", "content": " x" * middle}]
        tokens = count_prompt(candidate) + count_metadata(candidate, {}) + 512 + 64
        if tokens <= MAX_CONTEXT_TOKENS:
            low = middle
        else:
            high = middle
    exact = [{"role": "user", "content": " x" * low}]
    _install_openai(monkeypatch, lambda **kwargs: _response("ok"))
    client.complete(exact, max_tokens=512)
    with pytest.raises(BudgetExceeded):
        client.complete([{"role": "user", "content": " x" * high}], max_tokens=512)


def test_key_never_appears_in_errors_logs_or_reply(ca_cert, monkeypatch, caplog) -> None:
    secret = "trackb-test-key"
    client = LLMClient(api_key=secret, ca_cert=str(ca_cert))

    def explode(**kwargs):
        raise RuntimeError(f"upstream failed for {secret} in the body")

    _install_openai(monkeypatch, explode)
    with pytest.raises(LLMError) as caught:
        client.complete([{"role": "user", "content": "hi"}], max_tokens=16)
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)
    assert secret not in caplog.text

    def echo(**kwargs):
        return _response(f"pong {secret}")

    _install_openai(monkeypatch, echo)
    result = client.complete([{"role": "user", "content": "hi"}], max_tokens=16)
    assert secret not in result.text
    assert secret not in result.raw
    assert secret not in json.dumps(result.usage)


def test_429_backoff_is_2_4_then_stop(ca_cert, monkeypatch) -> None:
    sleeps = []
    monkeypatch.setattr("copilot.model_gateway.client.time.sleep", lambda seconds: sleeps.append(seconds))
    attempts = {"n": 0}

    def create(**kwargs):
        attempts["n"] += 1
        raise _status(429, "slow down")

    _install_openai(monkeypatch, create)
    client = LLMClient(api_key="trackb-test-key", ca_cert=str(ca_cert))
    with pytest.raises(LLMError):
        client.complete([{"role": "user", "content": "hi"}], max_tokens=16)
    assert attempts["n"] == 3
    assert sleeps == [2, 4]


def test_503_uses_the_same_backoff_and_500_does_not(ca_cert, monkeypatch) -> None:
    sleeps = []
    monkeypatch.setattr("copilot.model_gateway.client.time.sleep", lambda seconds: sleeps.append(seconds))
    attempts = {"n": 0}

    def create(**kwargs):
        attempts["n"] += 1
        raise _status(503)

    _install_openai(monkeypatch, create)
    client = LLMClient(api_key="trackb-test-key", ca_cert=str(ca_cert))
    with pytest.raises(LLMError):
        client.complete([{"role": "user", "content": "hi"}], max_tokens=16)
    assert attempts["n"] == 3
    assert sleeps == [2, 4]

    sleeps.clear()
    attempts["n"] = 0

    def create_500(**kwargs):
        attempts["n"] += 1
        raise _status(500)

    _install_openai(monkeypatch, create_500)
    with pytest.raises(LLMError):
        client.complete([{"role": "user", "content": "hi"}], max_tokens=16)
    assert attempts["n"] == 1
    assert sleeps == []


def test_thinking_mode_is_configurable(ca_cert, monkeypatch) -> None:
    seen = {}

    def create(**kwargs):
        seen.update(kwargs)
        return _response("ok")

    _install_openai(monkeypatch, create)
    client = LLMClient(
        api_key="trackb-test-key",
        ca_cert=str(ca_cert),
        thinking="chat_template_kwargs",
    )
    client.complete([{"role": "user", "content": "hi"}], max_tokens=16)
    assert seen["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}

    seen.clear()
    plain = LLMClient(api_key="trackb-test-key", ca_cert=str(ca_cert), thinking="no_think")
    plain.complete([{"role": "user", "content": "hi"}], max_tokens=16)
    assert seen["messages"][-1]["content"].endswith("/no_think")
    assert "extra_body" not in seen
