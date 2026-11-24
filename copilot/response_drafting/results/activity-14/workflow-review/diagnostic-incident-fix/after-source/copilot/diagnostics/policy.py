"""Constrain diagnostic decisions to symptoms evidenced by customer input."""
import re

from .facts import DiagnosticState


def allowed_decisions(state: DiagnosticState, query: str, api: str | None, pricing_requirements=None, *, enquiry=None):
    if enquiry is not None:
        from copilot.qualification.task import active_diagnostic_state, effective_customer_task

        state = active_diagnostic_state(state, enquiry, api)
        query = effective_customer_task(enquiry)
    values = {field: fact.value for field, fact in state.facts.items() if fact.status == "supplied"}
    text = query.casefold()
    code = str(values.get("error_code", "")).casefold()
    statuses = set(values.get("http_status", []))
    if values.get("proceed_without_more_questions"):
        return ["none"]
    evidence_decision = _additional_evidence_decision(query, api)
    if evidence_decision:
        return [evidence_decision]
    if values.get("user_agent_present") is False:
        return ["none"]
    if re.search(r"\bapi key\b.{0,35}\binvalid\b", text):
        return ["none"]
    if code == "request_denied" and _observed_denial(query):
        return ["none"] if _confirmed_key_cause(query) else ["request_reproduction"]
    if code == "nosegment" and values.get("coordinates"):
        return ["none"]
    if re.search(
        r"\b(?:never|not)\s+(?:returns?|getting|receiving)\b.{0,25}\b(?:query )?predictions?\b"
        r"|\bpredictions?\b.{0,25}\b(?:absent|missing|not returned)\b"
        r"|\bno\s+(?:query )?predictions?\s+(?:are\s+)?(?:returned|received)\b", text,
    ):
        return ["prediction_request"]
    if (re.search(r"\b(?:draw\w*|display\w*|shows?)\b", text)
            and re.search(r"\b(?:only(?:\s+(?:shows?|displays?|draws?))?\s+(?:one|1)|not (?:shown|drawn)|missing routes?)\b", text)):
        return ["display_result"]
    if code == "not_found" and (api == "distance_matrix" or "matrix" in text):
        return ["matrix_input"]
    if code == "zero_results" and (api == "reverse_geocode" or "reverse geocod" in text):
        return ["missing_results"]
    if (code == "over_query_limit" or "429" in statuses) and re.search(r"\b(?:loop\w*|burst\w*|concurren\w*|each pair)\b", text):
        return ["request_burst"]
    if statuses & {"401", "403"}:
        return ["request_reproduction"]
    if statuses & {"400", "422"}:
        return ["rejected_request"]
    if statuses:
        return ["none", "request_reproduction", "rejected_request"]
    if pricing_requirements and pricing_requirements.get("applicable"):
        return ["pricing_eligibility"]
    if re.search(r"\b(?:fails?|failing|errors?|reject\w*)\b", text):
        return ["none", "request_reproduction", "rejected_request"]
    return ["none"]


def _additional_evidence_decision(query, api):
    """Ask only for observed incidents, never a hypothetical or documentation example."""
    from copilot.safety.incident_evidence import observed_incidents

    evidence = observed_incidents(query)
    observed = evidence['observed_text']
    if not observed:
        return None
    exposed = evidence['credential_exposure']
    for clause in observed.splitlines():
        credential = re.search(r'\b(?:api[- ]?key|access[- ]?token|oauth[- ]?token|credentials?|secret)\b', clause, re.I)
        leaked = _positive_evidence(r'\bleak(?:ed|ing|age)?\b', clause)
        public = re.search(r'\b(?:public(?:ly)?|github|client[- ]side|frontend|browser)\b', clause, re.I)
        published = _positive_evidence(r'\b(?:exposed?|exposure|published|committed|visible)\b', clause)
        exposed = exposed or bool(credential and (leaked or public and published))
    if exposed:
        return 'credential_exposure'
    exhausted = _positive_evidence(
        r'\b(?:credits?|balance)\b.{0,45}\b(?:exhausted|depleted|empty|zero|0|used up)\b'
        r'|\b(?:ran|run|running)\s+out\s+of\s+(?:our\s+)?credits?\b'
        r'|\b(?:exhausted|depleted|used up)\b.{0,30}\b(?:credits?|balance)\b', observed,
    )
    stopped = _positive_evidence(r'\b(?:service|api|requests?|calls?|application)\b.{0,40}\b(?:stopped|down|blocked|failing|fail|suspended)\b', observed)
    restore = _positive_evidence(r'\b(?:restore|reactivate|resume|unblock|intervene|intervention)\b', query)
    if (exhausted and stopped or 'billing_incident' in evidence['categories']) and restore:
        return 'credit_restoration'
    autocomplete = api == 'autocomplete' or re.search(r'\b(?:autocomplete|auto[- ]?suggest|type[- ]?ahead|search box)\b', observed, re.I)
    incorrect = _positive_evidence(
        r'\b(?:wrong|incorrect|harmful|offensive|abusive|inappropriate|misleading|unsafe)\b.{0,45}\b(?:predictions?|suggestions?|results?)\b'
        r'|\b(?:predictions?|suggestions?|results?)\b.{0,45}\b(?:wrong|incorrect|harmful|offensive|abusive|inappropriate|misleading|unsafe)\b',
        observed,
    )
    if autocomplete and (incorrect or 'data_quality' in evidence['categories']):
        return 'prediction_quality'
    return None


def _positive_evidence(pattern, text):
    for match in re.finditer(pattern, text, re.I):
        prefix = re.split(r'[.!?;\n]', text[:match.start()])[-1]
        if re.search(r"\b(?:not|never|no|without)\b|n't\b", match.group(), re.I):
            continue
        if re.search(
            r"\b(?:not|never|no|without|wasn't|isn't|hasn't|haven't|didn't|doesn't)\s+"
            r"(?:(?:been|being|ever|publicly|actually|returns?|returned|shows?|showing|produces?|produced|observed?|seen?|any)\s+){0,3}$",
            prefix, re.I,
        ):
            continue
        return True
    return False


def _observed_denial(query):
    # A status definition alone does not establish a customer failure.
    if re.search(r"\b(?:what (?:does|is)|meaning of)\s+[`\"']?REQUEST_DENIED\b|\bREQUEST_DENIED\b.{0,12}\bmean\b", query, re.I):
        return False
    return bool(re.search(
        r"\b(?:returns?|returned|returning|gives?|gave|getting|received?|seeing|reports?|reported|fails?|failed|failing)\b.{0,65}\bREQUEST_DENIED\b"
        r"|\bREQUEST_DENIED\b\s+(?:for|with|when|after)\b", query, re.I,
    ))


def _confirmed_key_cause(query):
    # Only customer statements establish a cause. Retrieved possibilities do not.
    return bool(re.search(
        r"\b(?:we|i|our request|the request)\b.{0,35}\b(?:omitted|omit|do not include|did not include|did not send)\b.{0,20}\b(?:api\s+)?key\b"
        r"|\bwithout\s+(?:our|an?|the)\s+(?:api\s+)?key\b"
        r"|\b(?:we|i)\s+(?:have not|haven['’]t|did not|didn['’]t)\s+enabled?\s+(?:the\s+)?Geocoding API\b"
        r"|\bGeocoding API\s+is\s+(?:not enabled|disabled)\s+(?:in|for)\s+(?:our|my)\s+project\b",
        query, re.I,
    ))
