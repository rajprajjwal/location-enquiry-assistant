"""Deterministic pre-extraction for the interpretation step.

Purpose: pull qualification spans and API keyword hits from user turns only.
Use case: the hits are prompt hints and, on the rules-only path, the output.
Example: ``"20,000 requests a month"`` becomes a monthly_volume hit of 20000.

Patterns for volume, timeline, provider, region, budget, constraints, and
use case are the eval-freeze-v2 mapper patterns. Intent keywords are loaded
from ``intent_keywords.json`` and apply only on the rules-only (abstain) path,
matched against the customer's quoted message. Team keywords stay empty, so
the fallback leaves team null.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mapping.map_gt import (
    extract_monthly_volume,
    extract_timeline,
)
from copilot.safety.provider_evidence import ambiguous_current_providers, current_provider_hit, provider_retractions
from copilot.qualification.workload import from_text as asserted_monthly_volume

_REGION_PATTERNS = (
    re.compile(r"\b(?:in|across|for|throughout)\s+India\b", re.I),
    re.compile(r"\bIndian\s+(?:cities|city|market|price|pricing)\b", re.I),
    re.compile(r"\bIndia(?:n)?\s+price list\b", re.I),
)

_BUDGET = re.compile(
    r"\b(?:budget(?:\s+of)?|we can spend|no more than|under)\s+"
    r"(₹\s*[\d,.]+|USD\s*[\d,.]+|\$\s*[\d,.]+|[₹$][\d,.]+)",
    re.I,
)

_CONSTRAINT = re.compile(
    r"\b(\d+\s+requests per second|\d+\s+rps|self-host(?:ed|ing)?|"
    r"on-prem(?:ise)?|no live traffic|without traffic)\b",
    re.I,
)

_USE_CASE_A = re.compile(r"\bWe are an?\s+([^.?\n]{3,80})")
_USE_CASE_B = re.compile(
    r"\bOur\s+((?:commercial\s+)?(?:delivery|logistics|ride[- ]?hailing|"
    r"navigation|fleet|dispatch)[^.,?\n]{0,60})",
    re.I,
)

_API_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("directions", re.compile(
        r"\b(?:directions?|turn[- ]by[- ]turn|driving\s+routes?|route\s+(?:requests?|instructions?|geometry))\b",
        re.I,
    )),
    ("distance_matrix", re.compile(
        r"\b(?:(?:distance|route|routing|travel[- ]time|transit|mapbox)\s+matri(?:x|ces)"
        r"|computeRouteMatrix|matri(?:x|ces)\s+(?:api|calls?|engine)"
        r"|\d+\s*[x×]\s*\d+\s+matri(?:x|ces))\b", re.I)),
    ("autocomplete", re.compile(
        r"\b(?:auto[- ]?complete|auto[- ]?suggest|type[- ]?ahead|mapbox\s+search\s+box"
        r"|places\s+(?:api\s+)?session\s+tokens?"
        r"|suggest(?:ions|ed|ing|s)?\b[^.!?\n]{0,75}\b(?:as|while)\s+"
        r"(?:users?|customers?|visitors?|people|they|we)\s+typ(?:e|es|ing)"
        r"|(?:on|with)\s+every\s+keystroke\s+for\s+(?:address\s+)?suggestions)\b", re.I)),
    ("reverse_geocode", re.compile(
        r"\b(?:reverse[- ]geocod\w*|(?:street\s+)?address\s+(?:from|for|at)\s+"
        r"(?:the\s+|a\s+pair\s+of\s+)?(?:coordinates|latitude\s+and\s+longitude))\b", re.I)),
)
_GENERIC_ROUTING = re.compile(r"\brouting\b", re.I)
_DIRECTIONAL_COMPARISON = re.compile(
    r"\b(?:(?:more|less|fewer|higher|lower|cheaper)\s+than|instead\s+of|rather\s+than)\b", re.I,
)
_PRICE_COMPARISON = re.compile(
    r"\b(?:which\b[^.!?\n]{0,80}\b(?:cheaper|costs?\s+less|lower\s+cost)"
    r"|(?:options?|providers?|vendors?|alternatives?)\s+and\s+(?:(?:their|the)\s+)?"
    r"(?:(?:monthly|annual|yearly)\s+)?(?:costs?|prices?|pricing)"
    r"|(?:is|are)\b[^.!?\n]{0,60}\bor\b[^.!?\n]{0,60}\b(?:cheaper|less\s+expensive|lower\s+cost))\b",
    re.I,
)
_PER_CALL_CAP = re.compile(
    r"\b(?:can|could)\b[^.!?\n]{0,65}\b(?:return|accept|handle|include)\s+"
    r"(?:up to\s+)?\d[\d,]*\s+(?:results?|suggestions?|elements?|coordinates?|waypoints?|origins?|destinations?)"
    r"\s+(?:per\s+(?:call|request)|in\s+(?:one|a single)\s+(?:call|request))\b",
    re.I,
)

_DECLINE = re.compile(
    r"\b(?:not\s+sure|unsure|leave\s+(?:that|it|this|the\s+\w+|\w+)\s+open|"
    r"don'?t\s+know|do\s+not\s+know)\b",
    re.I,
)

_FIELD_CUES = {
    "region": re.compile(r"\bregions?\b", re.I),
    "monthly_volume": re.compile(r"\b(?:monthly\s+volume|volumes?|requests?\s+per\s+month)\b", re.I),
    "current_provider": re.compile(r"\b(?:current\s+provider|providers?)\b", re.I),
    "timeline": re.compile(r"\b(?:timelines?|deadlines?|go[- ]?live)\b", re.I),
    "budget": re.compile(r"\bbudgets?\b", re.I),
    "technical_constraints": re.compile(r"\b(?:technical\s+constraints?|constraints?)\b", re.I),
    "decision_maker": re.compile(r"\bdecision[- ]?makers?\b", re.I),
    "use_case": re.compile(r"\buse[- ]?cases?\b", re.I),
}

# Intent fallback table (intent_keywords.json): built from the docs and the tune
# split of the §7 pool only. It is used ONLY on the rules-only (abstain) path; on
# the model path the model's intent wins (design §3). TEAM_KEYWORDS stays empty.
_KW_PATH = Path(__file__).resolve().parent / "intent_keywords.json"
_WRAPPED = re.compile(r'(?:Customer wrote|Customer message):\s*["\u201c](.+?)["\u201d]', re.S)


def _load_intent_keywords() -> list[tuple[re.Pattern[str], str]]:
    data = json.loads(_KW_PATH.read_text(encoding="utf-8"))
    return [(re.compile(pattern, re.I | re.M), label) for label, pattern in data["rules"]]


INTENT_KEYWORDS: list[tuple[re.Pattern[str], str]] = _load_intent_keywords()
TEAM_KEYWORDS: list[tuple[re.Pattern[str], str]] = []


def customer_text(text: str) -> str:
    """The quoted customer message inside a CRM/ticket wrapper, else the text itself."""
    match = _WRAPPED.search(text or "")
    return match.group(1) if match else (text or "")


def explicit_intent(text: str) -> str | None:
    """Resolve direct cost comparisons and per-call capacity questions."""
    question = customer_text(text)
    if _PRICE_COMPARISON.search(question):
        return "pricing_comparison"
    if _PER_CALL_CAP.search(question):
        return "coverage_limits"
    return None


def is_decline_value(text: str) -> bool:
    """True when the whole phrase declines a fact and states no positive value."""
    if not text or not isinstance(text, str):
        return False
    if not _DECLINE.search(text):
        return False
    if extract_timeline(text) or extract_monthly_volume(text):
        return False
    return len(text.strip()) <= 120


def _field_cues(text: str) -> set[str]:
    return {field for field, cre in _FIELD_CUES.items() if cre.search(text or "")}


def _named_declines(text: str) -> set[str]:
    if not _DECLINE.search(text or ""):
        return set()
    return _field_cues(text)


def _region_hit(text: str) -> dict | None:
    for pattern in _REGION_PATTERNS:
        match = pattern.search(text)
        if match:
            return {"value": "India", "span": match.group(0)}
    return None


def _budget_hit(text: str) -> dict | None:
    match = _BUDGET.search(text)
    if not match:
        return None
    return {"value": match.group(0).strip(), "span": match.group(0).strip()}


def _constraint_hit(text: str) -> dict | None:
    match = _CONSTRAINT.search(text)
    if not match:
        return None
    return {"value": match.group(0).strip(), "span": match.group(0).strip()}


def _use_case_hit(text: str) -> dict | None:
    match = _USE_CASE_A.search(text)
    if match:
        value = match.group(1).strip().rstrip(",")
        return {"value": value, "span": match.group(0).strip()}
    match = _USE_CASE_B.search(text)
    if match:
        value = match.group(0)[4:].strip()
        return {"value": value, "span": match.group(0).strip()}
    return None


def _timeline_hit(text: str) -> dict | None:
    value = extract_timeline(text)
    if not value:
        return None
    return {"value": value.strip(), "span": value.strip()}


def _volume_hit(text: str) -> dict | None:
    parsed = asserted_monthly_volume(text)
    if not parsed:
        return None
    return {"value": parsed, "span": parsed["raw"]}


def _provider_hit(text: str) -> dict | None:
    hit = current_provider_hit(text)
    return {"value": hit['value'], "span": hit['span']} if hit else None


def _api_hits(text: str) -> list[dict]:
    hits = []
    for name, pattern in _API_PATTERNS:
        match = pattern.search(text)
        if match:
            hits.append({"api": name, "span": match.group(0)})
    if not any(hit["api"] == "directions" for hit in hits):
        routing = _GENERIC_ROUTING.search(text)
        if routing:
            hits.append({"api": "directions", "span": routing.group(0)})
    return hits


def _specific_api_families(hits: list[dict]) -> set[str]:
    return {hit["api"] for hit in hits if not _GENERIC_ROUTING.fullmatch(hit["span"])}


def _comparison_subject(text: str) -> str | None:
    """Use an explicit API in the main clause of an asymmetric comparison."""
    clauses = _DIRECTIONAL_COMPARISON.split(text, maxsplit=1)
    if len(clauses) != 2:
        return None
    subject, comparator = (_specific_api_families(_api_hits(clause)) for clause in clauses)
    if len(subject) == len(comparator) == 1 and subject != comparator:
        return next(iter(subject))
    return None


def _keyword(text: str, table: list[tuple[re.Pattern[str], str]]) -> str | None:
    for pattern, label in table:
        if pattern.search(text):
            return label
    return None


def _extract_user_text(text: str) -> dict:
    question = customer_text(text)
    return {
        "text": text,
        "region": _region_hit(text),
        "monthly_volume": _volume_hit(text),
        "current_provider": _provider_hit(text),
        "provider_retractions": provider_retractions(text),
        "provider_ambiguous": ambiguous_current_providers(text),
        "timeline": _timeline_hit(text),
        "budget": _budget_hit(text),
        "technical_constraints": _constraint_hit(text),
        "use_case": _use_case_hit(text),
        "api_hits": _api_hits(question),
        "declines": _named_declines(text),
        "intent": _keyword(question, INTENT_KEYWORDS),
        "team": _keyword(text, TEAM_KEYWORDS),
    }


def _as_turn(turn: Any) -> dict:
    if isinstance(turn, dict):
        return {"role": turn.get("role"), "text": turn.get("text") or ""}
    return {"role": getattr(turn, "role", None), "text": getattr(turn, "text", "") or ""}


def extract(history: list[Any], query: str) -> dict:
    """Extract from user turns only. ``history`` is oldest first and may include assistant turns.

    An unscoped decline ("leave that open") is applied to a field named in the
    immediately previous assistant turn. Assistant text is never mined for values.
    """
    user_turns: list[dict] = []
    previous_assistant: str | None = None
    for raw in history or []:
        turn = _as_turn(raw)
        if turn["role"] == "assistant":
            previous_assistant = turn["text"]
            continue
        if turn["role"] != "user":
            continue
        parsed = _extract_user_text(turn["text"])
        if is_decline_value(turn["text"]) and not parsed["declines"] and previous_assistant:
            parsed["declines"] = _field_cues(previous_assistant)
        user_turns.append(parsed)
        previous_assistant = None
    current = _extract_user_text(query or "")
    if is_decline_value(query or "") and not current["declines"] and previous_assistant:
        current["declines"] = _field_cues(previous_assistant)
    user_turns.append(current)

    all_hits = [{**hit, "turn": index} for index, turn in enumerate(user_turns) for hit in turn["api_hits"]]
    from . import seam

    found = {hit["api"] for hit in all_hits}
    ordered = [name for name in seam.load_vocab().apis if name in found]
    current_apis = _specific_api_families(current["api_hits"])
    # A newly named operation takes precedence. A bare follow-up uses the earlier API evidence.
    candidates = current_apis or _specific_api_families(all_hits) or found
    unique = next(iter(candidates)) if len(candidates) == 1 else _comparison_subject(customer_text(query or ""))
    return {
        "user_turns": user_turns,
        "api_hits": all_hits,
        "api_families": ordered,
        "unique_api": unique,
    }


def to_hints(extraction: dict) -> dict:
    """JSON-safe rule hits for the prompt. Values are spans, not invented labels."""
    hints: dict[str, Any] = {}
    if extraction["api_hits"]:
        hints["api"] = extraction["api_hits"]
    if extraction["unique_api"] is not None:
        hints["primary_api"] = extraction["unique_api"]
    fields = (
        "region",
        "monthly_volume",
        "current_provider",
        "timeline",
        "budget",
        "technical_constraints",
        "use_case",
    )
    for field in fields:
        spans = []
        for index, turn in enumerate(extraction["user_turns"]):
            hit = turn.get(field)
            if not hit:
                continue
            value = hit["value"]
            if isinstance(value, dict):
                value = value.get("raw")
            spans.append({"turn": index, "span": hit["span"], "value": value})
        if spans:
            hints[field] = spans
    if any(turn["declines"] for turn in extraction["user_turns"]):
        hints["declines"] = [
            {"turn": index, "fields": sorted(turn["declines"])}
            for index, turn in enumerate(extraction["user_turns"])
            if turn["declines"]
        ]
    return hints
