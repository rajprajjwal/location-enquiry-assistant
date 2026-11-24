"""Recognize usable monthly API workload without inventing periods or units."""
import math
import re
from mapping.map_gt import _parse_volume_number, extract_monthly_volume

_COUNT = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s*(?:k|thousand|m|mn|million|lakhs?|lac|crores?))?'
_UNITS = r'requests?|calls?|lookups?|sessions?|elements?|searches|search|queries|query|transactions?|matrices|matrix'
_PERIOD = r'(?:a\s+month|per\s+month|monthly|each\s+month|every\s+month|/\s*month|/\s*mo\b)'
_ALLOWED = {f'{unit}_per_month' for unit in ['requests','calls','lookups','sessions','elements','searches','queries','transactions','matrices']}
_RANGE = re.compile(_COUNT + r'\s*[–−-]\s*' + _COUNT + r'\s*(?:' + _UNITS + r')?\s*' + _PERIOD, re.I)
_OTHER_PERIOD = re.compile(r'\b(?:per|each|every|a)\s+(?:second|minute|hour|day|week|year)\b|/\s*(?:second|minute|hour|day|week|year|sec|s\b)|\b(?:daily|weekly|annually)\b', re.I)
_PREFIX = re.compile(r'\bmonthly\s+(?:usage|volume|workload|total)\s*(?:is|of|[:=])?\s*(?P<count>'+_COUNT+r')\s+(?P<unit>'+_UNITS+r')\b',re.I)
_DIRECT = re.compile(r'(?<![\d.−–-])(?P<count>'+_COUNT+r')\s+(?:(?:address[- ]search|API|routing|route|reverse[- ]geocoding|geocoding|autocomplete)\s+){0,3}(?P<unit>'+_UNITS+r')\s*'+_PERIOD,re.I)
_MATRIX = re.compile(r'\bmatri(?:ces|x(?:\s+(?:calls|requests))?)\s*[,;:]?\s*(?P<count>'+_COUNT+r')\s*'+_PERIOD,re.I)


def _number(value):
    return not isinstance(value, bool) and isinstance(value, (int,float)) and math.isfinite(value) and value >= 0


def from_text(text):
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


def normalize_monthly_volume(value):
    if isinstance(value,str):
        return from_text(value)
    if not isinstance(value,dict):
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
