"""Resolve the active customer task without importing unrelated history symptoms."""
import re

_NEW_TOPIC = re.compile(r'\b(?:switch|change)\s+(?:the\s+)?topics?\b|\b(?:new|separate|unrelated)\s+(?:question|topic|enquiry|request)\b', re.I)
_CONTINUATION = re.compile(
    r"^\s*(?:actually|correction|also|additionally|and\b|yes\b|no\b|not decided|"
    r"please\s+(?:proceed|continue)|go ahead|let['’]s leave|still\b|same\b|"
    r"what about|how about|what else|before\b|for (?:that|this)|we\s+(?:need|require|want)|"
    r"our\s+(?:monthly|peak)|the\s+(?:request|response|coordinates|volume|rate))",
    re.I,
)
_REFERENCE = re.compile(r'\b(?:earlier|previous|already said|what I told|that issue|this issue|same request|that request|it still|those results)\b', re.I)
_QUOTE = re.compile(r'\b(?:estimate|quote|cost|pricing|price|cheaper|billing)\b', re.I)
_DIAGNOSTIC = re.compile(r'\b(?:HTTP\s*[45]\d\d|REQUEST_DENIED|OVER_QUERY_LIMIT|ZERO_RESULTS|NoSegment|NOT_FOUND|fails?|failing|errors?|not returned|no predictions)\b', re.I)
_RECOMMENDATION = re.compile(r'\b(?:recommend|before choosing|before selecting|qualif\w*)\b', re.I)
_REQUEST = re.compile(r'^\s*(?:what|which|how|why|when|where|can|could|should|would|do|does|is|are|please\s+(?:explain|show|tell|calculate|estimate|compare)|explain|describe|show|tell|calculate|estimate|quote|compare|recommend)\b', re.I)
_OBSERVATIONS = {
    'http_status', 'error_code', 'coordinates', 'request_example', 'request_body', 'error_message',
    'result_filters', 'observed_api_result', 'input_pair', 'input_representation',
    'isolated_request_outcome', 'failure_after_credential_rotation', 'user_agent_present',
    'limit_parameter', 'waypoint_lower_bound_exclusive', 'ticket_id',
    'proceed_without_more_questions',
    'account_reference', 'prediction_query', 'returned_prediction', 'exposure_time', 'unusual_usage_spikes',
}


def _api(text):
    from copilot.enquiry_interpretation.rules import extract

    return extract([], text)['unique_api']


def _kind(text):
    from copilot.enquiry_workflow.routing import asks_qualification

    if _DIAGNOSTIC.search(text):
        return 'diagnostic'
    quote_request = '?' in text or _REQUEST.search(text) or re.match(
        r'^\s*(?:actually[,:]?\s*)?(?:please\s+)?(?:estimate|calculate|quote|compare|price)\b', text, re.I)
    if _QUOTE.search(text) and quote_request:
        return 'quote'
    if _RECOMMENDATION.search(text) or asks_qualification(text):
        return 'qualification'
    if '?' in text or _REQUEST.search(text):
        return 'documentation'
    return None


def _task_text(text):
    from copilot.enquiry_workflow.routing import customer_question

    return customer_question(text)


def active_task_sources(enquiry):
    """Retain a short follow-up with its task, but reset explicit new requests."""
    sources = [(f'history[{i}]', turn['text']) for i, turn in enumerate(enquiry.get('history', []))
               if turn['role'] == 'user']
    sources.append(('query', enquiry['query']))
    active = []
    api = kind = None
    for source, text in sources:
        meaning = _task_text(text)
        next_api, next_kind = _api(meaning), _kind(meaning)
        changed_api = api is not None and next_api is not None and api != next_api
        changed_kind = kind is not None and next_kind is not None and kind != next_kind
        statement = '?' not in meaning and not _REQUEST.search(meaning)
        continues = statement or len(meaning) <= 500 and bool(_CONTINUATION.search(meaning) or _REFERENCE.search(meaning))
        references_task = bool(_REFERENCE.search(meaning) or re.match(r'^\s*(?:what else|what other|anything else)\b', meaning, re.I))
        facts_prelude = bool(active) and kind is None
        if not active or _NEW_TOPIC.search(meaning) or changed_api or (changed_kind and not references_task) or not (continues or facts_prelude):
            active = []
            api = kind = None
        active.append((source, text))
        api = next_api or api
        kind = next_kind or kind
    return active


def effective_customer_task(enquiry):
    """Give decision selection the latest request plus its customer supplements."""
    return '\n'.join(_task_text(text) for _, text in active_task_sources(enquiry))


def task_scope_changed(enquiry):
    """An explicit topic or request boundary starts a fresh decision scope."""
    customer_turns = sum(turn['role'] == 'user' for turn in enquiry.get('history', [])) + 1
    return len(active_task_sources(enquiry)) < customer_turns or bool(_NEW_TOPIC.search(_task_text(enquiry['query'])))


def active_diagnostic_state(state, enquiry, api=None):
    """Return a decision-only view; the original state remains available for audit."""
    sources = active_task_sources(enquiry)
    text = '\n'.join(value for _, value in sources)
    active = state.model_copy(deep=True)
    reset = task_scope_changed(enquiry)
    for field in _OBSERVATIONS:
        fact = active.facts.get(field)
        if not fact:
            continue
        # Saved source='query' can refer to an earlier turn, so bind the evidence again.
        evidenced = bool(fact.evidence and fact.evidence in text)
        if not evidenced and reset:
            active.facts.pop(field, None)
    if reset:
        active.questions = [question for question in active.questions
                            if not set(question.facts) & _OBSERVATIONS]
        active.completed_checks = [check for check in active.completed_checks if check in text]
    return active
