"""Build field-level proposals for explicitly requested sandbox changes."""

import re

from copilot.case_storage.sandbox import diff
from copilot.rag.document_retrieval.query_analyzer import PROVIDER_KEYWORDS, detect

_TICKET_CATEGORIES = {
    "accuracy_question", "coverage_error", "error_resolution", "integration_question",
    "migration_question", "parameter_question", "performance_question", "policy_question", "response_fields",
}
_POLICY_QUESTION = re.compile(
    r"\b(?:licen[cs]\w*|usage.policy|terms of (?:use|service)|attribution|"
    r"public nominatim|nominatim\.openstreetmap\.org|cache .{0,35}(?:place ids?|results?))\b", re.I,
)
_RESPONSE_FIELDS = re.compile(
    r"\b(?:which|what|are|is)\b.{0,65}\b(?:units?|distance values?|actual values?|"
    r"raw (?:value|distance)|response fields?)\b", re.I,
)
_DISCOVERY = re.compile(r"\b(?:free allowance|free (?:calls|tier)|is .{0,35} free|billed per|bill .{0,45} one session)\b", re.I)


def record_target(query):
    ids = set(re.findall(r"\b(?:TKT|OPP)-\d{3,8}\b", query, re.I))
    wants_update = re.search(r"\b(?:update|propose|set|mark|change)\b", query, re.I)
    return next(iter(ids)).upper() if len(ids) == 1 and wants_update else None


def explicit_update_fields(query):
    fields = {}
    for field in ("status", "stage"):
        match = re.search(rf"\b{field}\s*(?:to|=)\s*([\w-]+(?:\s+[\w-]+){{0,2}}?)(?=[.!?,]|$)", query, re.I)
        if match:
            fields[field] = match.group(1)
    return fields


def _ticket_category(query, interpretation):
    if _POLICY_QUESTION.search(query):
        return "policy_question"
    if _RESPONSE_FIELDS.search(query):
        return "response_fields"
    sub_intent = interpretation.sub_intent
    if sub_intent in _TICKET_CATEGORIES:
        return sub_intent
    if sub_intent == "parameter_troubleshooting":
        return "parameter_question"
    if interpretation.intent == "troubleshooting":
        return "error_resolution"
    return sub_intent or interpretation.intent


def _providers(query, interpretation, comparison):
    named = detect(query)["providers"]
    if named:
        # Keep the customer's provider order in the proposed record.
        return sorted(named, key=lambda name: re.search("|".join(PROVIDER_KEYWORDS[name]), query, re.I).start())
    compared = (comparison or {}).get("providers") or []
    if compared:
        return compared
    provider = interpretation.qualification_details.current_provider
    return [provider] if provider else []


def update_request(query, interpretation, role, *, comparison=None, answer_ready=False):
    target = record_target(query)
    if not target:
        return None
    fields = explicit_update_fields(query)
    if fields:
        return {"record_id": target, "fields": fields}

    fields = {"owner": role.get("owner")}
    if interpretation.api:
        fields["api"] = interpretation.api
    if providers := _providers(query, interpretation, comparison):
        fields["providers"] = ", ".join(dict.fromkeys(providers))
    if target.startswith("TKT-"):
        fields["category"] = _ticket_category(query, interpretation)
        fields["severity"] = role.get("severity")
        if answer_ready:
            fields["status"] = "solution_proposed"
    elif answer_ready:
        dimensions = (comparison or {}).get("dimensions") or []
        drafted_quote = "pricing" in dimensions and interpretation.sub_intent not in {
            "billing_question", "free_tier_question",
        } and not _DISCOVERY.search(query)
        fields["stage"] = "quote_drafted" if drafted_quote else "discovery"
        fields["next_step"] = "send reviewed answer to customer"
    fields = {key: value for key, value in fields.items() if value is not None}
    return {"record_id": target, "fields": fields} if fields else None


def build_proposal(request, current):
    changes = diff(current, request["fields"])
    return {**request, "mode": "propose", "diff": changes} if changes else None
