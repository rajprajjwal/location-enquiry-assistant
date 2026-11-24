"""Recognize usable monthly API workload without inventing periods or units."""
import math
import re
from mapping.map_gt import _parse_volume_number, extract_monthly_volume

_COUNT = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s*(?:k|thousand|m|mn|million|lakhs?|lac|crores?))?'
_UNITS = r'requests?|calls?|lookups?|sessions?|elements?|searches|search|queries|query|transactions?|matrices|matrix|routes?'
_PERIOD = r'(?:a\s+month|per\s+month|monthly|each\s+month|every\s+month|/\s*month|/\s*mo\b)'
_ALLOWED = {f'{unit}_per_month' for unit in ['requests','calls','lookups','sessions','elements','searches','queries','transactions','matrices','routes']}
_RANGE = re.compile(_COUNT + r'\s*[–−-]\s*' + _COUNT + r'\s*(?:' + _UNITS + r')?\s*' + _PERIOD, re.I)
_OTHER_PERIOD = re.compile(r'\b(?:per|each|every|a)\s+(?:second|minute|hour|day|week|year)\b|/\s*(?:second|minute|hour|day|week|year|sec|s\b)|\b(?:daily|weekly|annually)\b', re.I)
_PREFIX = re.compile(r'\bmonthly\s+(?:usage|volume|workload|total)\s*(?:is|of|[:=])?\s*(?P<count>'+_COUNT+r')\s+(?P<unit>'+_UNITS+r')\b',re.I)
_MODIFIER = r'(?:address[- ]search|API|routing|route|reverse[- ]geocoding|geocoding|autocomplete|traffic[- ]aware|two[- ]wheeler|Google|Maps|Platform|Mapbox|Ola|Mappls|OSRM|Nominatim)'
_DIRECT = re.compile(r'(?<![\d.−–-])(?P<count>'+_COUNT+r')\s+(?:'+_MODIFIER+r'\s+){0,5}(?P<unit>'+_UNITS+r')\s*'+_PERIOD,re.I)
_MATRIX = re.compile(r'\bmatri(?:ces|x(?:\s+(?:calls|requests))?)\s*[,;:]?\s*(?P<count>'+_COUNT+r')\s*'+_PERIOD,re.I)
_CLAUSE = re.compile(r'[!?;\n]|(?<!\d)\.(?!\d)|\b(?:but|however|whereas)\b', re.I)
_UNCERTAIN = re.compile(r'\b(?:if|assuming|assume|suppose|hypothetical(?:ly)?|may|might|could|maybe|possibly|perhaps|whether|would|should)\b', re.I)
_QUESTION = re.compile(r'^\s*(?:what|which|how|do|does|did|is|are|will|would|should|can|could)\b', re.I)
_DOCUMENTED = re.compile(r'\b(?:docs?|documentation|manual|pricing page|free tier|allowance|quota|capacity)\b|\b(?:usage|request|rate|monthly|provider|API|service)\s+limits?\b|\blimits?\s*(?:is|of|[:=])?\s*\d|\b(?:allows?|permits?|supports?)\b|\b(?:provider|API|service|product|plan|tier|package|contract|subscription|Google|Mapbox|Ola|Mappls)\b.{0,45}\b(?:includes?|offers?)\b', re.I)
_NEGATED = re.compile(r"\b(?:not|never|no longer|don't|doesn't|won't|cannot|can't|do not|does not|will not)\b", re.I)
_SCENARIO = re.compile(r'\b(?:assuming|assume|suppose|hypothetical(?:ly)?|for (?:an?|this) estimate)\b', re.I)
_PRICING = re.compile(r'\b(?:estimate|cost|price|pricing|charges?|bill(?:ing)?|pay|options?|compare|vs|versus)\b', re.I)
_ESTIMATE_REQUEST = re.compile(r'^\s*(?:please\s+)?(?:estimate|calculate|price|quote|compare)\b', re.I)


def _number(value):
    return not isinstance(value, bool) and isinstance(value, (int,float)) and math.isfinite(value) and value >= 0


def _parse_quantity(text):
    if not isinstance(text,str) or _RANGE.search(text):
        return None
    parsed=extract_monthly_volume(text)
    if parsed and parsed['unit'] in _ALLOWED:
        start=text.find(parsed['raw'])
        if start > 0 and text[start-1] in '-−–':
            return None
        return parsed
    for pattern in (_PREFIX,_MATRIX,_DIRECT):
        match=pattern.search(text)
        if not match:
            continue
        unit=match.groupdict().get('unit') or 'matrices'
        is_matrix=unit.casefold() in {'matrix','matrices'}
        if unit.casefold() in {'route', 'routes'}:
            return {'raw': match.group(), 'requests_per_month': _parse_volume_number(match.group('count')),
                    'unit': 'routes_per_month'}
        parsed=extract_monthly_volume(f"{match.group('count')} {'calls' if is_matrix else unit} per month")
        if parsed:
            return {**parsed,'raw':match.group(),'unit':'matrices_per_month' if is_matrix else parsed['unit']}
    # Keep matrix operation counts distinct from origin-destination elements.
    direct=re.search(r'(?<![\d.−–-])(?P<count>'+_COUNT+r')\s+(?P<unit>matrices|matrix)\s*'+_PERIOD,text,re.I)
    if direct:
        return {'raw':direct.group(),'requests_per_month':_parse_volume_number(direct.group('count')),'unit':'matrices_per_month'}
    if re.search(r'\b(?:matrix|matrices)\b', text, re.I):
        operations=re.search(r'(?<![\d.−–-])(?P<count>'+_COUNT+r')\s+times\s*'+_PERIOD,text,re.I)
        if operations:
            return {'raw':operations.group(),'requests_per_month':_parse_volume_number(operations.group('count')),'unit':'matrices_per_month'}
    return None


def _clauses(text):
    start = 0
    for boundary in _CLAUSE.finditer(text):
        yield text[start:boundary.start()], boundary.group()
        start = boundary.end()
    yield text[start:], ''


def _usable(clause):
    return not (_DOCUMENTED.search(clause) or _NEGATED.search(clause))


def asserted_workload_evidence(text, evidence, start=None):
    """Check the enclosing clause so a short quote cannot hide a limit or assumption."""
    if not isinstance(evidence, str) or not evidence.strip():
        return False
    offset = 0
    for clause, ending in _clauses(text):
        position = clause.find(evidence)
        if position >= 0 and (start is None or offset + position == start):
            return not (ending == '?' or _QUESTION.search(clause) or _ESTIMATE_REQUEST.search(clause)
                        or _UNCERTAIN.search(clause) or not _usable(clause))
        offset += len(clause) + len(ending)
    return False


def from_text(text):
    """Read asserted monthly quantities; questions and published limits are unknown."""
    if not isinstance(text, str):
        return None
    result = None
    for clause, ending in _clauses(text):
        if ending == '?' or _QUESTION.search(clause) or _ESTIMATE_REQUEST.search(clause) or _UNCERTAIN.search(clause) or not _usable(clause):
            continue
        parsed = _parse_quantity(clause)
        if parsed:
            result = parsed
    return result


def scenario_volume_from_text(text):
    """Keep explicit estimate inputs separate from confirmed customer workload."""
    if not isinstance(text, str):
        return None
    estimate_requested = _PRICING.search(text) and ('?' in text or _ESTIMATE_REQUEST.search(text))
    result = None
    for clause, ending in _clauses(text):
        scenario = _SCENARIO.search(clause) or _ESTIMATE_REQUEST.search(clause) or (
            estimate_requested and (ending == '?' or _QUESTION.search(clause) or _UNCERTAIN.search(clause)))
        if scenario and _usable(clause) and (parsed := _parse_quantity(clause)):
            result = {**parsed, 'basis': 'scenario_assumption', 'evidence': clause.strip()}
    return result


def scenario_volume_from_enquiry(enquiry):
    """Return the latest customer-authored estimate assumption, never assistant text."""
    sources = [(f'history[{i}]', turn['text']) for i, turn in enumerate(enquiry.get('history', [])) if turn['role'] == 'user']
    sources.append(('query', enquiry['query']))
    for source, text in reversed(sources):
        if parsed := scenario_volume_from_text(text):
            return parsed, source
    return None, None


def normalize_monthly_volume(value):
    if isinstance(value,str):
        return from_text(value)
    if not isinstance(value,dict):
        return None
    if value.get('basis') == 'scenario_assumption':
        return None
    raw=value.get('raw')
    parsed=from_text(raw)
    if parsed:
        return parsed
    count=value.get('requests_per_month'); unit=value.get('unit')
    if not isinstance(raw,str) or not _number(count) or unit not in _ALLOWED or _OTHER_PERIOD.search(raw):
        return None
    # A normalized stored quantity may retain only its numeric span as raw text.
    if unit == 'matrices_per_month':
        operations=re.fullmatch(r'(?P<count>'+_COUNT+r')\s+times\s*'+_PERIOD,raw,re.I)
        if operations and _parse_volume_number(operations.group('count')) == count:
            return {'raw':raw,'requests_per_month':count,'unit':unit}
    bare=_parse_volume_number(raw)
    if bare is not None and bare == count:
        return {'raw':raw,'requests_per_month':count,'unit':unit}
    return None


def monthly_volume_from_enquiry(enquiry):
    sources=[(f'history[{i}]',turn['text']) for i,turn in enumerate(enquiry.get('history',[])) if turn['role']=='user']
    sources.append(('query',enquiry['query']))
    for source,text in reversed(sources):
        parsed=from_text(text)
        if parsed:
            return parsed,source
    return None,None


def monthly_volume_proposal(value,evidence):
    parsed=from_text(evidence)
    if not parsed:
        return None
    proposed=normalize_monthly_volume(value)
    count=proposed['requests_per_month'] if proposed else (_parse_volume_number(value) if isinstance(value,str) else value)
    if not _number(count) or count != parsed['requests_per_month']:
        return None
    if proposed and proposed['unit'] != parsed['unit']:
        return None
    return parsed
