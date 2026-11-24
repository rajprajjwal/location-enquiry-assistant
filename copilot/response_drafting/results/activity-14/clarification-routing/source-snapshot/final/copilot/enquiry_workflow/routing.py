"""Resolve answerable questions before asking for sales qualification fields."""
import re

from copilot.rag.document_retrieval.query_analyzer import detect

from .document_guidance import guidance_kind

_PRICE = re.compile(r"\b(?:cost|prices?|pricing|quote|charges?|billing|billed|cheapest|price[- ]?list)\b", re.I)
_ESTIMATE = re.compile(r"\b(?:estimate|estimated|quote|calculate|how much|cheapest|monthly cost|cost per month|what (?:would|will|does) .{0,70} cost)\b", re.I)
_QUALIFY = re.compile(r"\bwhat (?:else )?(?:should|must|do|would|will|information|details|questions)\b.{0,70}\b(?:ask|clarify|confirm|qualify|need before|need to know)\b", re.I)
_DISCOVERY = re.compile(r"\b(?:which|what|any)\b.{0,90}\b(?:providers?|apis?|services?|geocoders?|options?|platforms?|alternatives?)\b", re.I)
_MIXED_QUESTION = re.compile(r"\b(?:and|also)\s+(?:when|how|why|which|can|does|would|is)\b", re.I)
_QUALIFICATION_TOPIC = re.compile(r"\b(?:what|which)\b.{0,85}\b(?:requirements|details|questions|information)\b.{0,40}\b(?:clarify|confirm|ask|gather)\b", re.I)
_CUSTOMER = re.compile(r'\bcustomer (?:wrote|asks?|said|message)\s*:\s*["“](.*?)["”](?:\s|$)', re.I | re.S)


_COMPARE = re.compile(r"\b(?:compare|versus|vs)\b", re.I)
_CONTINUE = re.compile(r"\b(?:go ahead|proceed|earlier|previous|first message|already said|what I told|leave that open)\b", re.I)


def customer_question(query):
    match = _CUSTOMER.search(query)
    return match[1].strip() if match else query


def asks_qualification(query):
    return bool(_QUALIFY.search(query) or _QUALIFICATION_TOPIC.search(query))


def discovers_providers(query):
    return bool(_DISCOVERY.search(query))


def broad_provider_search(query):
    return bool(re.search(
        r"\bwhich\b.{0,55}\b(?:providers?|alternatives?|apis?|geocoders?|services?)\b"
        r"|\b(?:other options|other providers|alternatives? to)\b", query, re.I,
    ))


def allows_partial_answer(query):
    return bool(broad_provider_search(query) or query.count("?") > 1 or _MIXED_QUESTION.search(query))


def answerable_question(query):
    return guidance_kind(query) is not None or bool(
        (not asks_qualification(query) or _MIXED_QUESTION.search(query)) and (
            "?" in query or re.match(r"\s*(?:explain|describe|compare|show|tell)\b", query, re.I)
        )
        and (detect(query)["apis"] or detect(query)["providers"])
    )


def asks_for_estimate(question, context, pricing_intent):
    from copilot.pricing_tools.pricing_intent import regex_hints

    hints = regex_hints(context)
    workload = any(key in hints for key in ("volume", "sessions", "matrix", "users_typing"))
    explicit = bool(_ESTIMATE.search(context))
    result = not asks_qualification(question) and (
        explicit and bool(_PRICE.search(context)) or pricing_intent and workload and (
            _PRICE.search(context) or _COMPARE.search(context)
        )
    )
    return bool(result), workload


def prior_customer_question(history):
    for turn in reversed(history):
        if turn.get("role") == "user" and turn.get("text", "").strip():
            return customer_question(turn["text"])
    return ""


def documentation_context(question, earlier):
    if earlier and len(question) <= 320 and _CONTINUE.search(question):
        return f"{earlier}\nLatest customer reply: {question}"
    return question


def pricing_context(question, earlier, pricing_intent):
    from copilot.pricing_tools.pricing_intent import regex_hints

    confirms_sku = re.search(r"\b(?:new|legacy)\b.{0,35}\bSKU\b", question, re.I)
    continues_pricing = _CONTINUE.search(question) or _ESTIMATE.search(question) or confirms_sku or (
        pricing_intent and not answerable_question(question)
    )
    if not continues_pricing:
        return question
    kinds = {"volume", "sessions", "matrix", "users_typing"}
    if earlier and len(question) <= 320 and not kinds.intersection(regex_hints(question)):
        if kinds.intersection(regex_hints(earlier)) and (
            _PRICE.search(earlier) or _ESTIMATE.search(earlier) or pricing_intent and _COMPARE.search(earlier)
        ):
            return f"{question}\nEarlier customer request: {earlier}"
    return question



def additional_answer_request(query):
    return bool(re.search(r"\b(?:also|and|then|additionally)\s+(?:compare|explain|calculate|estimate|show|tell|describe|provide)\b", query, re.I))


def documentation_providers(query):
    """Use names in an explicit documentation request, not incidental history."""
    from copilot.enquiry_interpretation.seam import load_vocab

    if _PRICE.search(query):
        return []
    canonical = set(load_vocab().providers)
    for clause in re.split(r'[.!?;\n]|\bbut\b', query, flags=re.I):
        request = re.search(r"\b(?:what|which)\s+(?:do|does)\b[^.!?;\n]{0,240}?\b(?:document|support|offer|return)\b", clause, re.I)
        scope = request.group() if request else None
        if scope is None:
            comparison = _COMPARE.search(clause) or re.search(r"\b(?:each|every) provider\b", clause, re.I)
            if comparison and re.search(r"\b(?:docs?|documentation|documented|parameters?)\b", clause, re.I):
                verb = re.search(r'\bcompare\b', clause, re.I)
                scope = clause[verb.start():] if verb else clause
        if scope:
            providers = list(dict.fromkeys(p for p in detect(scope)['providers'] if p in canonical))
            if len(providers) >= 2:
                return providers
    return []
