"""Keep routine request checks in first-line support during ownership assessment."""
import re

_ASSESSMENT = re.compile(r"\bwho should own\b|\bdoes it need escalat", re.I)
_CUSTOMER = re.compile(r'^\s*customer message\s*:\s*["“](.*?)["”]', re.I | re.S)
_REQUEST_ISSUE = re.compile(
    r"\b(?:INVALID_REQUEST|REQUEST_DENIED|MAX_ROUTE_LENGTH_EXCEEDED|ZERO_RESULTS|duration_in_traffic)\b"
    r"|\b(?:invalid|missing)[ /-]+(?:origin|destination|parameter|coordinate)\b"
    r"|\b(?:URLs?|URI|request[- ]line)\b.{0,140}\b(?:too long|length limit|too large)\b"
    r"|\brejects?\b.{0,45}\b(?:request|matrix)\b", re.I,
)
_INTERVENTION = re.compile(
    r"\b(?:human|hand[- ]?off|forward|connect|refer|transfer|escalat\w*|second[- ]line|L2|urgent|security|exposed|leaked|compromised|"
    r"persistent|repeated|sustained|regression|outage)\b"
    r"|\bproduction\b.{0,35}\b(?:down|degraded|failing|blocked)\b"
    r"|\ball (?:our )?(?:production )?(?:requests|customers|users)\b", re.I,
)


def routine_support_assessment(query, *, customer_status="unknown"):
    if customer_status == "new" or not _ASSESSMENT.search(query):
        return False
    match = _CUSTOMER.match(query)
    if not match:
        return False
    message = match[1]
    return bool(_REQUEST_ISSUE.search(message) and not _INTERVENTION.search(message))
