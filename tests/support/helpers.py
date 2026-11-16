"""Shared fixtures for interpretation tests. Not production code."""

from __future__ import annotations

import json

from copilot.llm.client import DEFAULT_MODEL, Completion

QUAL_KEYS = (
    "use_case",
    "region",
    "monthly_volume",
    "current_provider",
    "timeline",
    "budget",
    "technical_constraints",
    "decision_maker",
)


def model_payload(**overrides) -> dict:
    qual = {key: {"value": None, "evidence": None} for key in QUAL_KEYS}
    if "qualification" in overrides:
        for key, value in overrides.pop("qualification").items():
            qual[key] = value
    payload = {
        "intent": "docs_how_to",
        "sub_intent": "parameter_question",
        "api": "directions",
        "team": "Support",
        "confidence": {"intent": 0.4, "api": 0.7, "team": 0.5},
        "qualification": qual,
    }
    payload.update(overrides)
    return payload


def model_json(**overrides) -> str:
    return json.dumps(model_payload(**overrides))


def completion(text: str, *, latency_ms: int = 7) -> Completion:
    return Completion(
        text=text,
        raw=text,
        model=DEFAULT_MODEL,
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        latency_ms=latency_ms,
        think_seen="<think>" in text.lower(),
    )


class ScriptedClient:
    """Returns queued completions or raises queued exceptions."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, messages, *, max_tokens, temperature):
        self.calls.append(
            {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        )
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
