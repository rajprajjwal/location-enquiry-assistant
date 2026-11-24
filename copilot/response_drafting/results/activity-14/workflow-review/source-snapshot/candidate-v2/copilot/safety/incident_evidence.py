"""Validate customer incident evidence using the shared escalation-rule categories."""
import re

from .escalation import _rules

_RESOLVED = re.compile(
    r'\b(?:(?:we|I)\s+(?:have\s+)?(?:already\s+)?(?:fixed|resolved|restored|corrected)'
    r'|(?:has|have)\s+(?:already\s+)?been\s+(?:fixed|resolved|restored|corrected)'
    r'|(?:is|was)\s+(?:already\s+)?(?:fixed|resolved|restored|corrected)'
    r'|already\s+(?:fixed|resolved|restored|corrected))\b', re.I,
)
_ACTION_REQUEST = re.compile(
    r'^\s*(?:please\s+)?(?:restore|reactivate|resume|unblock|intervene)\b'
    r'|\b(?:we|I)\s+(?:want|need|request|ask)\b.{0,50}\b(?:restor\w*|reactivat\w*|resum\w*|unblock\w*|interven\w*)\b', re.I,
)
_CREDENTIAL = re.compile(r'\b(?:api[- ]?key|access[- ]?token|oauth[- ]?token|credentials?|secret)\b', re.I)


def _positive_match(clause, match):
    text = match.group()
    if re.search(r"\b(?:not|never|no|without)\b|n't\b", text, re.I) and not re.fullmatch(r'not\s+working', text, re.I):
        return False
    prefix = clause[:match.start()]
    if re.search(r'\bno\s+(?:(?:returned|autocomplete|API|customer)\s+){0,2}(?:results?|predictions?|suggestions?|localit(?:y|ies)|calls?|requests?|service)\s*$', prefix, re.I):
        return False
    return not re.search(
        r"\b(?:not|never|no|without|wasn't|isn't|hasn't|haven't|didn't|doesn't)\s+"
        r"(?:(?:been|being|ever|publicly|actually|return(?:s|ed|ing)?|show(?:s|ing)?|produce(?:s|d)?|observed?|seen?|any)\s+){0,4}$",
        prefix, re.I,
    )


def observed_incidents(query):
    """Return asserted category evidence; this does not choose an owner or route."""
    from copilot.qualification.extraction import clauses, _customer_clause

    observations = []
    for offset, clause, ending in clauses(query):
        if not _customer_clause(clause, ending) or _ACTION_REQUEST.search(clause):
            continue
        resolved = next((match for match in _RESOLVED.finditer(clause) if _positive_match(clause, match)), None)
        uncertain_resolution = re.search(r"\b(?:not sure|cannot confirm|can't confirm|don't know|do not know)\b", clause, re.I)
        if resolved and not uncertain_resolution:
            # A completed remedy closes earlier observations, not a later new incident.
            observations = []
            continue
        observations.append((offset, clause))

    observed = '\n'.join(clause for _, clause in observations)
    categories = {}
    for rule in _rules():
        if any(pattern.search(observed) for pattern in rule['_not']):
            continue
        signals = []
        for name, patterns in (('any', rule['_any']), ('and_any', rule['_and'])):
            matches = []
            for offset, clause in observations:
                for pattern in patterns:
                    for match in pattern.finditer(clause):
                        if _positive_match(clause, match):
                            matches.append({'condition': name, 'text': match.group(),
                                            'start': offset + match.start(), 'end': offset + match.end()})
            if name == 'any' and not matches or name == 'and_any' and patterns and not matches:
                signals = []
                break
            signals.extend(matches)
        if signals:
            categories[rule['category']] = signals
    exposed = False
    for offset, clause in observations:
        if not _CREDENTIAL.search(clause):
            continue
        for signal in categories.get('security_incident', []):
            if signal['condition'] != 'any' or not (offset <= signal['start'] and signal['end'] <= offset + len(clause)):
                continue
            leaked = re.search(r'\bleak(?:ed|ing|age)?\b|\bexposed?\b|\bstolen\b|\bcompromis', signal['text'], re.I)
            public_commit = (re.search(r'\bpublic(?:ly)?\b', clause, re.I)
                             and re.search(r'\b(?:github|repo)\b', signal['text'], re.I)
                             and _CREDENTIAL.search(signal['text']))
            if leaked or public_commit:
                exposed = True
    return {'observed_text': observed, 'categories': categories, 'credential_exposure': exposed}
