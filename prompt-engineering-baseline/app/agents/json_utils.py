# Source history: Raj Kumar (a3ef3a6); see source-history.json.
"""
Robust JSON extraction for LLM output.

Qwen3 (and most chat models) frequently return JSON wrapped in ```json fences,
prefixed by <think>...</think> reasoning, surrounded by prose, or (on errors /
truncation) an empty string. json.loads() on any of those raises
"Expecting value: line 1 column 1 (char 0)". These helpers never raise.
"""
import json
import re
from typing import Any, Optional

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def extract_json(raw: Optional[str]) -> Optional[dict]:
    """Return the first JSON object found in raw LLM text, or None."""
    if not raw or not raw.strip():
        return None
    text = _THINK_RE.sub("", raw).strip()
    # Unclosed <think> (truncated output) — drop everything up to the last tag
    if "<think>" in text.lower():
        text = text[text.lower().rfind("</think>") + len("</think>"):] if "</think>" in text.lower() else ""
    candidates = [m.group(1).strip() for m in _FENCE_RE.finditer(text)] + [text]

    decoder = json.JSONDecoder()
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            pass
        # Scan for the first decodable {...} block inside surrounding prose
        for i, ch in enumerate(cand):
            if ch != "{":
                continue
            try:
                obj, _ = decoder.raw_decode(cand, i)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, dict):
                return obj
    return None


def invoke_json(llm, messages: list, fallback: Any) -> tuple[dict, str]:
    """
    Invoke the LLM and parse a JSON object from its reply.
    Retries once if the reply is empty or contains no parsable JSON.
    Returns (parsed_or_fallback, last_raw_text). LLM transport errors propagate.
    """
    raw = ""
    for _ in range(2):
        raw = llm.invoke(messages).content or ""
        parsed = extract_json(raw)
        if parsed is not None:
            return parsed, raw
    return (fallback(raw) if callable(fallback) else fallback), raw
