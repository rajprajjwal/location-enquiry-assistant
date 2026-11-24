"""Describe uncertainty in routine ownership without changing the enquiry route."""

import re

from copilot.enquiry_interpretation.rules import is_decline_value
from copilot.safety.escalation_policy import customer_status

from .routing import customer_question, documentation_context, pricing_context, prior_customer_question

_STATUS_QUESTION = re.compile(
    r"\b(?:new|existing)\b.{0,60}\b(?:customer|project|account)\b"
    r"|\balready\b.{0,45}\b(?:using|use|customer)\b",
    re.I,
)
_CUSTOMER_QUESTION = re.compile(
    r"\b(?:new|existing)\b.{0,60}\bcustomer\b|\balready\b.{0,45}\bcustomer\b", re.I,
)
_USAGE_QUESTION = re.compile(r"\balready\b.{0,45}\b(?:using|use)\b", re.I)
_SETUP_TARGET = re.compile(r"\b(?:project|(?:api[ -]?)?key|token|credential|account|setup)\b", re.I)


def _customer_relationship_question(question):
    if _CUSTOMER_QUESTION.search(question):
        return True
    usage = _USAGE_QUESTION.search(question)
    if not usage:
        return False
    target = re.split(r"[?,;]|\b(?:with|through|via|under|for)\b", question[usage.end():], maxsplit=1, flags=re.I)[0]
    return bool(target.strip()) and not _SETUP_TARGET.search(target)


def customer_status_reply(query, question='', *, bound=False):
    """Bind a short answer only to one customer-status question."""
    if not bound and not _customer_relationship_question(question):
        return None
    if question and (not _customer_relationship_question(question) or question.count('?') > 1
        or ';' in question or re.search(
            r'\b(?:and|also|or)\s+(?:what|which|how|when|where|why|do|does|should|can|is|are|would|will|have)\b'
            r'|\band\b.{0,60}\b(?:monthly volume|currency|requests|rate|region|country|budget|timeline)\b',
            question, re.I,
        )):
        return None
    answer = query.strip().casefold().rstrip('.!')
    if answer in {'existing', 'existing customer', 'already using it'}:
        return 'existing'
    if answer in {'new', 'new customer', 'evaluating it'}:
        return 'new'
    if answer not in {'yes', 'no'} or not question:
        return None
    # A yes/no answer cannot resolve an either/or choice or a negated question.
    if re.search(r"\b(?:new|not|never|no longer)\b|n't\b", question, re.I):
        return None
    existing = re.search(r'\bexisting\s+customer\b|\balready\b.{0,35}\b(?:using|use)\b', question, re.I)
    if existing:
        return 'existing' if answer == 'yes' else 'new'
    return None


def review_customer_status(query, history, interpretation, confirmed_customer_status=None):
    """Retain status evidence and explicit deferrals across case turns."""
    latest = customer_question(query)
    earlier = prior_customer_question(history)
    context = documentation_context(latest, earlier)
    if interpretation.intent in {"pricing_quote", "pricing_comparison"}:
        context = pricing_context(context, earlier, pricing_intent=True)
    if confirmed_customer_status not in {None, "unknown", "existing", "new"}:
        raise ValueError("Confirmed customer status must be existing, new, or unknown.")
    confirmed = confirmed_customer_status in {"existing", "new"}
    status = confirmed_customer_status if confirmed else customer_status(context)
    deferred = False
    previous_assistant = ""
    turns = [*history, {"role": "user", "text": latest}]
    for index, turn in enumerate(turns):
        text = turn.get("text", "")
        if turn["role"] == "assistant":
            previous_assistant = text
            continue
        if turn["role"] != "user":
            continue
        explicit = customer_status(customer_question(text))
        reply = customer_status_reply(text, previous_assistant)
        if reply is not None:
            explicit = reply
        if confirmed and index < len(turns) - 1:
            previous_assistant = ""
            continue
        if explicit != "unknown":
            status = explicit
            deferred = False
        elif _STATUS_QUESTION.search(previous_assistant) and is_decline_value(text):
            status = "unknown"
            deferred = True
        previous_assistant = ""
    deferred = deferred and status == "unknown"
    return status, deferred


def ownership_review(query, history, interpretation, routing, confirmed_customer_status=None):
    status, deferred = review_customer_status(query, history, interpretation, confirmed_customer_status)
    provisional = status == "unknown" and not routing["should_escalate"]
    if provisional:
        message = ("Customer status was deferred. "
                   if deferred else "Customer status is unknown. ")
        reason = message + f"Provisional owner: {routing['owner']}. " + routing["reason"]
    else:
        reason = routing["reason"]
    return {
        "customer_status": status,
        "owner": routing["owner"],
        "provisional": provisional,
        "status_deferred": deferred,
        "confirmation_needed": provisional,
        "reason": reason,
        "suggested_question": (
            "Are you already using this service, or evaluating it as a new customer?"
            if provisional and not deferred else None
        ),
    }
