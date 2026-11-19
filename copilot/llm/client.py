"""Thin wrapper over the pinned openai SDK for the VM07 Qwen endpoint.

Purpose: one serialized chat call with fail-closed config, token limits, and
429/503 backoff. The interpretation step is the caller.
Use case: ``python -m copilot.llm.client --smoke`` sends one short request.
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
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://103.42.50.41:1031/v1"
DEFAULT_MODEL = "Qwen/Qwen3-8B"
MAX_COMPLETION_TOKENS = 1024
MAX_CONTEXT_TOKENS = 8192
BACKOFF_SECONDS = (2, 4, 8)
THINKING_MODES = ("chat_template_kwargs", "no_think", "off")

# One active request per key, including across client instances in this process.
_CALL_LOCK = threading.Lock()

_THINK_MARK = re.compile(r"<think>", re.IGNORECASE)


class ConfigError(Exception):
    """Missing or unusable endpoint configuration. Raised before any network call."""


class TokenLimitError(Exception):
    """``max_tokens`` is outside the endpoint's 1–1024 range."""


class BudgetExceeded(Exception):
    """Estimated input tokens plus ``max_tokens`` is above 8192.

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
    """APPROVED interim count: ceil(characters / 4). Empty text is 0."""
    n = len(text or "")
    return math.ceil(n / 4) if n else 0


def estimate_input_tokens(messages: list[dict]) -> int:
    """Estimate prompt tokens from role and content, joined by newlines.

    This is the same ceil(chars/4) method the context-limit check uses.
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
        """Send one logical chat call. Retries 429/503 after 2s, 4s, then 8s."""
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
        estimated = estimate_input_tokens(outgoing)
        if tools or response_format:
            estimated += estimate_text_tokens(json.dumps(
                {"tools": tools, "response_format": response_format}, ensure_ascii=False, sort_keys=True
            ))
        if estimated + max_tokens > MAX_CONTEXT_TOKENS:
            raise BudgetExceeded(
                f"estimated input tokens {estimated} + max_tokens {max_tokens} "
                f"exceeds {MAX_CONTEXT_TOKENS}"
            )
        started = time.perf_counter()
        with _CALL_LOCK:
            response = self._call_with_backoff(outgoing, max_tokens, temperature, extra)
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

    def _call_with_backoff(self, messages, max_tokens, temperature, extra) -> object:
        last: Exception | None = None
        attempts = len(BACKOFF_SECONDS) + 1
        for attempt in range(attempts):
            try:
                return self._once(messages, max_tokens, temperature, extra)
            except ConfigError:
                raise
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                if status not in (429, 503):
                    self._raise_scrubbed(exc, status_code=status if isinstance(status, int) else None)
                last = exc
                if attempt >= len(BACKOFF_SECONDS):
                    break
                delay = BACKOFF_SECONDS[attempt]
                time.sleep(delay)
        self._raise_scrubbed(last, status_code=getattr(last, "status_code", None))

    def _once(self, messages, max_tokens, temperature, extra) -> object:
        import httpx
        import openai

        try:
            context = ssl.create_default_context(cafile=self._ca_cert)
            http_client = httpx.Client(verify=context, timeout=self._timeout)
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
    parser = argparse.ArgumentParser(prog="python -m copilot.llm.client")
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
