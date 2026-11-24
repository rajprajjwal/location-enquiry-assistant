"""Recognize continued billing-policy questions without assuming an outage."""
import re

from copilot.enquiry_interpretation.rules import is_decline_value
from copilot.enquiry_workflow.routing import customer_question, prior_customer_question

_BALANCE = re.compile(r"\b(?:credit balance|prepaid credits|account balance)\b", re.I)
_FUTURE_STOP = re.compile(
    r"\b(?:will|would|could|can)\b.{0,60}\b(?:calls|requests|routing|service)\b"
    r".{0,35}\b(?:stop|fail|be blocked|be suspended)\b", re.I,
)
_CONTINUE = re.compile(r"\b(?:proceed|go ahead|earlier|previous|first message|what I (?:already )?said)\b", re.I)
_INTERVENTION = re.compile(
    r"\b(?:human|hand[- ]?off|transfer|contact|connect|forward|refer|investigat\w*|restore|escalat\w*|urgent|security|exposed|leak\w*|compromis\w*|"
    r"refund|overcharg\w*|fraud|disput\w*|unauthori\w*|outage)\b"
    r"|\b(?:calls|requests|routing|service)\b(?:\s+\w+){0,4}\s+(?:stopped|failed|failing|blocked|suspended)\b"
    r"|\b(?:cannot|can't|unable to)\s+(?:route|send requests|use the service)\b"
    r"|\breview\s+(?:my|our|the)\s+account\b", re.I,
)


def billing_policy_continuation(query, history=()):
    latest = customer_question(query)
    earlier = prior_customer_question(history)
    if not earlier or len(latest) > 320 or not (is_decline_value(latest) or _CONTINUE.search(latest)):
        return False
    if _INTERVENTION.search(latest) or _INTERVENTION.search(earlier):
        return False
    return bool(_BALANCE.search(earlier) and _FUTURE_STOP.search(earlier))
