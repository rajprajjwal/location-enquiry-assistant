# Source history: extracted and extended from escalation_policy.py; original policy by Deepshikha (62db1b2).
"""Recognize asserted service use without treating a proposed integration as live."""
import re


def _asserted(message, position):
    prefix = re.split(r"[.!?;\n]", message[:position])[-1]
    if re.search(r"\b(?:if|whether|suppose|assuming|imagine|can|could|should|would|will|might|may|does|do)\b", prefix, re.I):
        return False
    return not re.search(r"\b(?:not|never|no longer|aren't|isn't)\s+(?:an?\s+)?$", prefix, re.I)


def customer_status(message, patterns, *, actual_use=True):
    explicit = [(match.start(), status) for status, pattern in patterns.items()
                for match in re.finditer(pattern, message, re.I) if _asserted(message, match.start())]
    if explicit:
        return max(explicit)[1]
    if not actual_use:
        return "unknown"
    from copilot.rag.document_retrieval.query_analyzer import detect

    requests = re.compile(
        r"\b(?:we\s+(?:(?:always|currently|already|regularly)\s+)?(?:send|pass|call|receive|get)"
        r"|our\s+(?:mobile\s+|web\s+|production\s+)?(?:app|application|integration|system)"
        r"\s+(?:currently\s+)?(?:calls|uses|requests|receives|returns))\b", re.I,
    )
    reported_error = re.compile(
        r"\b(?:returns?|gives?|getting|receiving)\s+"
        r"(?:(?:an?|the|HTTP|status|error|code|response)[: ]+){0,3}['\"]?"
        r"(?:ZERO_RESULTS|REQUEST_DENIED|INVALID_REQUEST|OVER_QUERY_LIMIT|(?<![\d,])(?:429|403|401|5\d\d)(?![\d,]))\b"
        r"|\b(?:doesn't|does not|isn't|is not)\s+return(?:ing)?\b", re.I,
    )
    for sentence in re.split(r"[.!?\n]", message):
        evidence = detect(sentence)
        if not (evidence["providers"] or evidence["apis"]):
            continue
        personal = re.search(
            r"\breturns?\s+(?!(?:operator|department|team|manager)\b).{0,90}"
            r"\b(?:for|from|with)\s+(?:our|my)\b", sentence, re.I,
        ) if not re.search(r"\b(?:if|unless|would|will|might|plan)\b", sentence, re.I) else None
        match = requests.search(sentence) or reported_error.search(sentence) or personal
        if match and _asserted(sentence, match.start()):
            return "existing"
    return "unknown"
