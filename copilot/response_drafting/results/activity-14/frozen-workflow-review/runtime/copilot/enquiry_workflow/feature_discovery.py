"""Identify provider-feature discovery under the approved provisional policy."""
import re

from copilot.rag.document_retrieval.query_analyzer import detect

_DISCOVERY = re.compile(
    r'\b(?:which|what|any)\s+(?:(?:of the|reverse[- ]geocoding|reverse|autocomplete|routing|'
    r'directions|matrix|distance|place|location|map|search|table|places|geocoding|the|available|'
    r'public|mapping)\s+){0,5}(?:providers?|vendors?|geocoders?|'
    r'APIs?(?!\s+(?:parameter|field|key|header|option|method)\b))\b', re.I,
)
_NAMED_COMPARISON = re.compile(r'\b(?:which of|what do|compare)\b', re.I)


def feature_discovery_reason(context, interpretation):
    """Discovery is a task decision, not proof of a new customer relationship."""
    if interpretation.intent not in {'capability_match', 'coverage_limits', 'sales_qualification', 'docs_how_to'}:
        return None
    # Numeric workload feasibility is a documented request-limit question.
    capacity = re.search(r'\b\d+(?:\s*[x×]\s*\d+)?\s*(?:stops?|elements?|origins?|destinations?|waypoints?|coordinates?|matri(?:x|ces))\b', context, re.I)
    per_request = re.search(r'\b(?:one|single|per|each)\s+(?:API\s+)?(?:call|request)\b|\bfewest (?:API )?calls\b', context, re.I)
    if capacity and per_request:
        return None
    providers = detect(context)['providers']
    discovery = (_DISCOVERY.search(context)
                 or (len(providers) >= 2 and _NAMED_COMPARISON.search(context))
                 or (interpretation.intent == 'capability_match' and not providers))
    if discovery:
        return 'Provider-feature discovery uses provisional Sales ownership while customer status remains unconfirmed.'
    return None
