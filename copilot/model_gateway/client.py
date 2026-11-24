"""Thin wrapper over the pinned openai SDK for the VM07 Qwen endpoint.

Purpose: one serialized chat call with fail-closed config, token limits, and
429/503 backoff. The interpretation step is the caller.
Use case: ``python -m copilot.model_gateway.client --smoke`` sends one short request.
Example: a missing ``TRACKB_API_KEY`` raises ``ConfigError`` before any HTTP call.

Thinking mode is configurable and unverified against the endpoint (design §4).
The post-check still strips ``<think>`` blocks. This module never logs the API key.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import ssl
import sys
import threading
import time

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential
from .reliability import active_query, query_scope, ReliabilityError
from .token_counting import count_prompt, count_metadata
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://103.42.50.41:1031/v1"
DEFAULT_MODEL = "Qwen/Qwen3-8B"
MAX_COMPLETION_TOKENS = 1024
MAX_CONTEXT_TOKENS = 8192
BACKOFF_SECONDS = (2, 4)
THINKING_MODES = ("chat_template_kwargs", "no_think", "off")

# One active request per key, including across client instances in this process.
_CALL_LOCK = threading.Lock()

_THINK_MARK = re.compile(r"<think>", re.IGNORECASE)


class ConfigError(Exception):
    """Missing or unusable endpoint configuration. Raised before any network call."""


class TokenLimitError(Exception):
    """``max_tokens`` is outside the endpoint's 1–1024 range."""


class BudgetExceeded(Exception):
    """The context, cumulative token budget, or enquiry deadline was exhausted.

    The interpretation step maps this to ``abstain_reason="budget_exceeded"``.
    """


class LLMError(Exception):
    """The endpoint failed. The message never contains the API key."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class Completion:
    """One chat completion. ``text`` is the raw assistant content, think blocks included."""

    text: str
    raw: str
    model: str
    usage: dict | None
    latency_ms: int
    think_seen: bool
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str | None = None


def estimate_text_tokens(text: str) -> int:
    """Legacy trace estimate; admission uses the published tokenizer."""
    n = len(text or "")
    return math.ceil(n / 4) if n else 0


def estimate_input_tokens(messages: list[dict]) -> int:
    """Estimate prompt tokens from role and content, joined by newlines.

    Retained for existing traces; admission uses the published tokenizer.
    """
    chunks: list[str] = []
    for message in messages:
        chunks.append(str(message.get("role", "")))
        content = message.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False, sort_keys=True)
        chunks.append(content)
        metadata = {key: value for key, value in message.items() if key not in {"role", "content"}}
        if metadata:
            chunks.append(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    return estimate_text_tokens("\n".join(chunks))


def _scrub(secret: str, text: str) -> str:
    if not text:
        return ""
    if secret:
        text = text.replace(secret, "[REDACTED]")
        bearer = f"Bearer {secret}"
        text = text.replace(bearer, "Bearer [REDACTED]")
    return text


class LLMClient:
    """Chat client. ``base_url`` defaults to the VM07 endpoint and ignores ``OPENAI_*``."""

    def __init__(
        self,
        *,
        base_url: str | None = DEFAULT_BASE_URL,
        api_key: str | None = None,
        ca_cert: str | None = None,
        model: str = DEFAULT_MODEL,
        thinking: str = "chat_template_kwargs",
        timeout: float = 60.0,
    ):
        # Explicit arguments win. Environment fallbacks are TRACKB_* only.
        if api_key is None:
            api_key = os.environ.get("TRACKB_API_KEY")
        if ca_cert is None:
            ca_cert = os.environ.get("TRACKB_CA_CERT")
        if not base_url:
            raise ConfigError("base_url is not configured")
        if not api_key:
            raise ConfigError("TRACKB_API_KEY is not set")
        if not ca_cert:
            raise ConfigError("TRACKB_CA_CERT is not set")
        if not os.path.isfile(ca_cert):
            raise ConfigError("TRACKB_CA_CERT path does not exist")
        if thinking not in THINKING_MODES:
            raise ConfigError(f"unknown thinking mode: {thinking}")
        self._base_url = base_url
        self._api_key = api_key
        self._ca_cert = ca_cert
        self._model = model
        self._thinking = thinking
        self._timeout = timeout

    def __repr__(self) -> str:
        return (
            f"LLMClient(base_url={self._base_url!r}, model={self._model!r}, "
            f"thinking={self._thinking!r})"
        )

    @query_scope()
    def complete(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 512,
        temperature: float = 0,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        response_format: dict | None = None,
    ) -> Completion:
        """Send one logical call with at most two shared step retries."""
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
            raise TokenLimitError("max_tokens must be an integer")
        if max_tokens < 1 or max_tokens > MAX_COMPLETION_TOKENS:
            raise TokenLimitError(
                f"max_tokens must be 1..{MAX_COMPLETION_TOKENS}, got {max_tokens}"
            )
        outgoing = self._prepare_messages(messages)
        if tool_choice is not None and not tools:
            raise ConfigError("tool_choice requires tools")
        extra = self._thinking_extra()
        for name, value in (
            ("tools", tools), ("tool_choice", tool_choice), ("response_format", response_format)
        ):
            if value is not None:
                extra[name] = value
        try:
            prompt_tokens = count_prompt(outgoing, tools=tools, thinking=self._thinking != "chat_template_kwargs")
            overhead = count_metadata(outgoing, extra)
        except (OSError, ValueError) as exc:
            raise ConfigError("The Qwen3 prompt could not be counted; check tokenizer assets and message structure.") from exc
        if prompt_tokens + max_tokens + overhead + 64 > MAX_CONTEXT_TOKENS:
            active_query().event("context_budget")
            raise BudgetExceeded("Exact prompt plus requested output exceeds the model context.")
        started = time.perf_counter()
        session = active_query()
        if not _CALL_LOCK.acquire(timeout=session.remaining()):
            session.event("query_timeout")
            raise BudgetExceeded("Enquiry deadline reached while waiting for the model.")
        try:
            from .request_gate import request_gate
            try:
                with request_gate(self._base_url, self._api_key, timeout=session.remaining()):
                    response = self._call_with_backoff(outgoing, max_tokens, temperature, extra)
            except TimeoutError:
                session.event("model_key_wait_timeout")
                raise BudgetExceeded("Enquiry deadline reached waiting for the shared model key.") from None
        finally:
            _CALL_LOCK.release()
        latency_ms = int(round((time.perf_counter() - started) * 1000))
        text = self._message_text(response)
        text = _scrub(self._api_key, text)
        usage = self._usage(response)
        model = _scrub(self._api_key, getattr(response, "model", None) or self._model)
        choices = getattr(response, "choices", None) or []
        message = getattr(choices[0], "message", None) if choices else None
        tool_calls = []
        for call in getattr(message, "tool_calls", None) or []:
            function = getattr(call, "function", None)
            tool_calls.append({
                "id": _scrub(self._api_key, getattr(call, "id", "") or ""),
                "type": getattr(call, "type", "function"),
                "function": {
                    "name": _scrub(self._api_key, getattr(function, "name", "") or ""),
                    "arguments": _scrub(self._api_key, getattr(function, "arguments", "") or ""),
                },
            })
        return Completion(
            text=text,
            raw=text,
            model=model,
            usage=usage,
            latency_ms=latency_ms,
            think_seen=bool(_THINK_MARK.search(text)),
            tool_calls=tool_calls,
            finish_reason=getattr(choices[0], "finish_reason", None) if choices else None,
        )

    def _prepare_messages(self, messages: list[dict]) -> list[dict]:
        copied = [dict(message) for message in messages]
        if self._thinking == "no_think":
            if copied and copied[-1].get("role") == "user" and isinstance(copied[-1].get("content"), str):
                copied[-1]["content"] = copied[-1]["content"].rstrip() + "\n/no_think"
            else:
                copied.append({"role": "user", "content": "/no_think"})
        return copied

    def _thinking_extra(self) -> dict:
        # Unverified against VM07 (design §4). chat_template_kwargs is the default;
        # no_think appends the soft switch; off sends neither.
        if self._thinking == "chat_template_kwargs":
            return {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
        return {}

    @staticmethod
    def _retryable(exc):
        return (getattr(exc, "status_code", None) in {429, 503}
                or isinstance(exc, TimeoutError)
                or type(exc).__name__ in {"APITimeoutError", "APIConnectionError", "ReadTimeout", "ConnectTimeout"})

    def _call_with_backoff(self, messages, max_tokens, temperature, extra) -> object:
        session = active_query()
        tokens = count_prompt(messages, tools=extra.get("tools"),
                              thinking=self._thinking != "chat_template_kwargs")
        tokens += max_tokens + count_metadata(messages, extra) + 64
        retries = Retrying(stop=stop_after_attempt(session.retry_allowance() + 1), retry=retry_if_exception(self._retryable),
                           wait=wait_exponential(multiplier=2, min=2, max=4),
                           sleep=session.pause, reraise=True)
        try:
            for attempt in retries:
                with attempt:
                    if attempt.retry_state.attempt_number > 1:
                        session.retry()
                    session.reserve(tokens)
                    try:
                        response = self._once(messages, max_tokens, temperature, extra)
                        usage = self._usage(response)
                        if usage and isinstance(usage.get("total_tokens"), int):
                            with session.lock:
                                session.observed_tokens += usage["total_tokens"]
                        session.check()
                        return response
                    except Exception as exc:
                        session.event("model_error", error_type=type(exc).__name__,
                                      status_code=getattr(exc, "status_code", None))
                        raise
        except ReliabilityError as exc:
            raise BudgetExceeded(str(exc)) from None
        except ConfigError:
            raise
        except Exception as exc:
            self._raise_scrubbed(exc, status_code=getattr(exc, "status_code", None))

    def _once(self, messages, max_tokens, temperature, extra) -> object:
        import httpx
        import openai

        try:
            context = ssl.create_default_context(cafile=self._ca_cert)
            session = active_query()
            timeout = min(self._timeout, session.limits.model_timeout_seconds, session.remaining())
            http_client = httpx.Client(verify=context, timeout=timeout)
        except (ssl.SSLError, OSError):
            raise ConfigError("TRACKB_CA_CERT could not be loaded") from None
        try:
            sdk = openai.OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                http_client=http_client,
                max_retries=0,
            )
            kwargs = {
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            kwargs.update(extra)
            return sdk.chat.completions.create(**kwargs)
        finally:
            http_client.close()

    def _raise_scrubbed(self, exc: Exception | None, *, status_code: int | None) -> None:
        raw = "" if exc is None else str(exc)
        detail = _scrub(self._api_key, raw) or exc.__class__.__name__ if exc else "endpoint error"
        if self._api_key and self._api_key in detail:
            detail = detail.replace(self._api_key, "[REDACTED]")
        raise LLMError(detail, status_code=status_code) from None

    @staticmethod
    def _message_text(response: object) -> str:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        return content or ""

    @staticmethod
    def _usage(response: object) -> dict | None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }


def smoke() -> int:
    """One short call. Prints model, latency, usage, think-block flag, and reply."""
    try:
        client = LLMClient()
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        comp = client.complete(
            [{"role": "user", "content": "Reply with the single word pong."}],
            max_tokens=16,
            temperature=0,
        )
    except (BudgetExceeded, TokenLimitError, LLMError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"model: {comp.model}")
    print(f"latency_ms: {comp.latency_ms}")
    print(f"usage: {json.dumps(comp.usage, sort_keys=True)}")
    print(f"think_block: {str(comp.think_seen).lower()}")
    print(f"reply: {comp.text}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m copilot.model_gateway.client")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="send one short chat completion and print model, latency, usage, and reply",
    )
    args = parser.parse_args(argv)
    if not args.smoke:
        parser.error("--smoke is required")
    return smoke()


if __name__ == "__main__":
    raise SystemExit(main())
