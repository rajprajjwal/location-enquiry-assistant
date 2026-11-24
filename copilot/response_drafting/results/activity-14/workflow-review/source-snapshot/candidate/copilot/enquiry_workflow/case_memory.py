"""Rebuild conversation state from the saved turns of one case."""
import json
import re

from copilot.enquiry_interpretation import rules
from copilot.conversation_state import ConversationState


_FIELDS = ("region", "monthly_volume", "current_provider", "timeline", "budget",
           "technical_constraints", "decision_maker")
_COMPLETED_CHECK = re.compile(
    r"^(?:(?:we|i)\s+(?:have\s+)?(?:already\s+)?|already\s+)"
    r"(?:checked|verified|tested|tried|confirmed|restarted|retried|rotated|cleared)\b", re.I,
)


def turn_event(query, *, facts=None, questions=(), missing=(), awaiting=(), issue=None, timestamp=None):
    analysed = rules.extract([], query)
    turn = analysed["user_turns"][-1]
    captured = {name: hit["value"] for name in _FIELDS if (hit := turn.get(name))}
    api = analysed["unique_api"]
    if api:
        captured["use_case_api"] = {"api": api, "use_case": (turn["use_case"] or {}).get("value")}
    captured.update(facts or {})
    return {
        "facts": captured, "declined": sorted(turn["declines"]), "questions": list(questions),
        "provider_retractions": turn['provider_retractions'], "provider_ambiguous": turn['provider_ambiguous'],
        "missing": list(missing), "awaiting": list(awaiting), "issue": issue, "timestamp": timestamp,
        "diagnostics": [
            line.strip() for line in re.split(r"[.!?](?:\s+|$)|\n", query)
            if _COMPLETED_CHECK.search(line.strip()) and len(line.strip()) <= 300
        ],
    }


def _same_value(field, old, new):
    if field == "monthly_volume" and isinstance(old, dict) and old.get("requests_per_month") is not None:
        return (old.get("requests_per_month"), old.get("unit")) == (new.get("requests_per_month"), new.get("unit"))
    return old == new


def _apply(state, event):
    if event.get("diagnostic_state") is not None:
        from copilot.diagnostics.facts import DiagnosticState
        state.diagnostic_state = DiagnosticState.model_validate(event["diagnostic_state"]).model_dump(mode="json")
    for field in event["declined"]:
        state.known_facts.pop(field, None)
        state.remove_missing_information(field)
    revoked = event.get('provider_retractions', [])
    ambiguous = event.get('provider_ambiguous', False)
    if ambiguous or state.known_facts.get('current_provider') in revoked:
        state.known_facts.pop('current_provider', None)
    for field, value in event["facts"].items():
        if field == 'current_provider' and (ambiguous or value in revoked):
            continue
        if field in event["declined"]:
            continue
        previous = state.known_facts.get(field)
        if field == "use_case_api" and previous and previous["api"] == value["api"] and not value["use_case"]:
            value = {**value, "use_case": previous.get("use_case")}
        if previous is not None and not _same_value(field, previous, value):
            correction = state.apply_correction(field, value)
            if event.get("timestamp"):
                correction["timestamp"] = event["timestamp"]
        else:
            state.add_known_fact(field, value)
        if field in state.questions_asked:
            state.answer_question(field)
    for field in event["questions"]:
        state.ask_question(field)
    for check in event["diagnostics"]:
        if check.casefold() not in {line.casefold() for line in state.diagnostic_history}:
            state.add_diagnostic_step(check)
    if event.get("issue"):
        state.add_unresolved_issue(event["issue"])
    if event.get("awaiting"):
        state.unresolved_issues = [issue for issue in state.unresolved_issues if not issue.startswith("Awaiting ")]
        for field in event["awaiting"]:
            state.add_unresolved_issue(f"Awaiting {field.replace('_', ' ')}")
    unresolved = set(state.questions_asked) - set(state.questions_answered)
    state.missing_information = sorted((set(event["missing"]) | unresolved) - state.known_facts.keys())
    state.unresolved_issues = [
        issue for issue in state.unresolved_issues
        if not issue.startswith("Awaiting ") or issue.removeprefix("Awaiting ").replace(" ", "_") in unresolved
    ]


def load_conversation(con, case_id):
    state = ConversationState(case_id)
    rows = con.execute(
        "SELECT m.content, m.ts, s.output_json FROM messages AS m "
        "LEFT JOIN trace_steps AS s ON s.trace_id = m.turn_trace_id AND s.component = 'conversation_state' "
        "WHERE m.case_id = ? AND m.role = 'user' ORDER BY m.id", (case_id,),
    )
    updated_at = state.updated_at
    for row in rows:
        event = {**turn_event(row['content'], timestamp=row['ts']), **json.loads(row['output_json'])} if row['output_json'] else turn_event(row['content'], timestamp=row['ts'])
        _apply(state, event)
        if "diagnostic_state" not in event:
            from copilot.diagnostics.facts import build_diagnostic_state
            state.diagnostic_state = build_diagnostic_state(
                {"query": row["content"]}, state.diagnostic_state,
            ).model_dump(mode="json")
        updated_at = event.get("timestamp") or row["ts"]
    state.build_summary()
    state.updated_at = updated_at
    return state


def interpretation_facts(state):
    if state is None:
        return []
    return [{"field": field, "value": value, "source": "state_store"}
            for field, value in state.known_facts.items()]
