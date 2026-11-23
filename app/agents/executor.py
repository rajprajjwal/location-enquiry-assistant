from langchain.schema import SystemMessage, HumanMessage
from app.llm import get_llm
from app.kb.retriever import retrieve
from app.tools.validators import validate_location_request, classify_error_code
from app.agents.json_utils import extract_json
import json
import os
import re

EXECUTOR_SYSTEM = """You are a Location Services Copilot Executor.
Using the retrieved knowledge base excerpts and tool results provided, draft a helpful, accurate response.
- Ground every claim in the provided sources; cite them as [KB-1], [KB-2], etc.
- If information is not in the sources, say so explicitly.
- For sales: match requirements to capabilities, identify gaps, draft communications.
- For support: use diagnostic results to guide troubleshooting; list specific steps.
- Extract any tracker field updates from the conversation (JSON block at end labelled TRACKER_UPDATES).
- Propose a structured handoff summary if the conversation indicates a transfer.

Format:
RESPONSE:
<your drafted response>

TRACKER_UPDATES:
{"field": "value", ...}  (empty dict if none)
"""


# Named third-party map providers the KB may be asked about. The KB only holds
# anonymised "Provider A/B/C" material, so these names are normally absent.
# Display name -> pattern matched (case-insensitive) in the user message and the sources.
THIRD_PARTY_PROVIDERS = {
    "Ola Maps": r"\bola(\s*maps?)?\b",
    "Google Maps": r"\bgoogle\s*maps?\b",
    "Mapbox": r"\bmapbox\b",
    "TomTom": r"\btom\s*tom\b",
    "HERE Maps": r"\bhere\s*maps?\b",
    "OpenStreetMap": r"\bopen\s*street\s*maps?\b|\bosm\b",
    "Apple Maps": r"\bapple\s*maps?\b",
    "Azure Maps": r"\bazure\s*maps?\b",
}


def kb_gap_notice(user_message: str, kb_results: list) -> str:
    """Deterministic disclaimer when the user names providers absent from the retrieved sources."""
    corpus = " ".join(r.get("content", "") for r in kb_results)
    missing = [name for name, pat in THIRD_PARTY_PROVIDERS.items()
               if re.search(pat, user_message, re.IGNORECASE)
               and not re.search(pat, corpus, re.IGNORECASE)]
    if not missing:
        return ""
    names = ", ".join(missing)
    return (
        f"Note: the knowledge base has no information about {names}, so I can't compare "
        "them from the available sources. It only documents our service (Provider A) "
        "against anonymised competitors (Provider B and Provider C) for directions, "
        "distance matrix, autocomplete, reverse geocoding and pricing. I can share that "
        "comparison instead, or escalate to a specialist for a named-provider comparison."
    )


def run_executor(workflow: str, user_message: str, history: list[dict],
                 planner_output: dict, params: dict | None = None) -> dict:
    llm = get_llm(temperature=0.2)

    # 1. Retrieve KB
    kb_results = retrieve(user_message, k=4)
    sources_text = "\n\n".join(f"[KB-{i+1}] {r['content']}" for i, r in enumerate(kb_results))

    # 2. Run deterministic validators if params provided
    validation_text = ""
    if params:
        if any(k in params for k in ["lat", "lon", "timestamp", "device_id"]):
            val = validate_location_request(params)
            validation_text = f"\nValidation results: {json.dumps(val)}"
        if "error_code" in params:
            ec = classify_error_code(params["error_code"])
            validation_text += f"\nError code analysis: {json.dumps(ec)}"

    # 3. Build prompt
    history_text = "\n".join(f"{m['role'].upper()}: {m['content'][:300]}" for m in history[-6:])
    prompt = f"""Workflow: {workflow}
Planner output: {json.dumps(planner_output)}
{validation_text}

Knowledge Base:
{sources_text}

Conversation history:
{history_text}

User message: {user_message}"""

    messages = [SystemMessage(content=EXECUTOR_SYSTEM), HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    result = _parse_executor_response(response.content, kb_results)
    result["kb_gap_notice"] = kb_gap_notice(user_message, kb_results)
    return result


def _parse_executor_response(raw: str, kb_results: list) -> dict:
    response_text = raw
    tracker_updates = {}

    if "TRACKER_UPDATES:" in raw:
        parts = raw.split("TRACKER_UPDATES:")
        response_text = parts[0].replace("RESPONSE:", "").strip()
        tracker_updates = extract_json(parts[1]) or {}
    elif "RESPONSE:" in raw:
        response_text = raw.replace("RESPONSE:", "").strip()

    source_file = lambda r: os.path.basename(r.get("source", "KB"))
    return {
        "draft_response": response_text,
        "tracker_updates": tracker_updates,
        "sources": [
            {"ref": f"KB-{i+1}", "content": r["content"][:150],
             "score": r["score"], "file": source_file(r)}
            for i, r in enumerate(kb_results)
        ],
    }
