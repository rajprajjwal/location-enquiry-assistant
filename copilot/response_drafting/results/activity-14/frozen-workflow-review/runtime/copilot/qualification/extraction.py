"""Extract explicit requirement assertions before optional model fact proposals."""
import re

_COUNT = r'(?<![\d.−–-])\d+(?:\s*[–-]\s*\d+)?'
_STOPS = r'(?:outlets|stops|waypoints)'
_ROUTE_COUNTS = [
    re.compile(r'(?P<value>'+_COUNT+r')\s+'+_STOPS+r'\s+(?:in|on|per|for)\s+(?:(?:one|a|each|single|every)\s+)?(?:route|request)\b', re.I),
    re.compile(r'\b(?:(?:each|one|single|every|a)\s+)?(?:route|request)\s+(?:has|includes|contains|visits|with|must\s+(?:visit|include))\s+(?P<value>'+_COUNT+r')\s+'+_STOPS+r'\b', re.I),
]
_STORAGE_COUNT = r'\d[\d,]*(?:\.\d+)?(?:\s*(?:k|m|mn|thousand|million|lakhs?))?'
_STORAGE_OBJECT = (r'(?:(?:the|our|their|these|those|all|any|some|returned)\s+)?'
                   r'(?:' + _STORAGE_COUNT + r'\s+)?(?:addresses|address|results?|responses?)\b')
_STORAGE = r'(?:stor(?:e|es|ing)|retain(?:s|ing)?|cach(?:e|es|ing)|sav(?:e|es|ing))\s+' + _STORAGE_OBJECT
_TRAFFIC = r'(?:live[- ]traffic|traffic[- ]aware(?:\s+(?:routing|ETAs?))?)\b'
_ELEMENTS = r'(?:address(?:es)?\s+(?:broken|split)\s+into\s+(?:elements|components)|(?:structured\s+)?address[- ](?:elements?|components?|breakdown))\b'
_ROOFTOP = r'(?:street[- ]address\s*\(rooftop\)|rooftop)(?:\s+(?:precision|accuracy))?\b'
_ASSERTIONS = {
    'storage_required': (
        r'\b(?:must|need(?:s)? to|will|want(?:s)? to|require(?:s)?(?: to)?)\s+'+_STORAGE,
        r"\b(?:do not|don't|does not|doesn't|will not|won't|never|must not)\s+(?:need to\s+)?"+_STORAGE,
    ),
    'traffic_required': (
        r'\b(?:under|with|need|needs|want|wants|require|requires)\s+'+_TRAFFIC,
        r"\b(?:do not|don't|does not|doesn't|will not|won't)\s+(?:need|want|require|use)\s+"+_TRAFFIC,
    ),
    'address_elements_required': (
        r'\b(?:need|needs|want|wants|require|requires|must have|must include|must return)\s+[^.?!;\n]{0,70}?'+_ELEMENTS,
        r"\b(?:do not|don't|does not|doesn't)\s+(?:need|want|require)\s+[^.?!;\n]{0,70}?"+_ELEMENTS,
    ),
    'rooftop_hard_filter': (
        r'(?:\bonly\s+(?:wants?|needs?|accepts?|requires?)\s+[^.?!;\n]{0,150}?'+_ROOFTOP+
        r'|\b(?:need|needs|require|requires|must have)\s+[^.?!;\n]{0,50}?rooftop[- ]only(?:\s+precision)?)',
        r"\b(?:do not|don't|does not|doesn't)\s+(?:need|want|require)\s+[^.?!;\n]{0,50}?"+_ROOFTOP+r'\s*(?:[- ]only|hard[- ]filter)',
    ),
}

_DETAILS_PRODUCT = r'(?P<product>Place\s+Details(?:\s+(?:Essentials|Pro|Enterprise)(?:\s*\+\s*Atmosphere)?)?)\b'
_DETAILS_END = re.compile(r'\b(?:end(?:s|ing)?|terminat(?:e|es|ing))\s+(?:in|with|by)\s+(?:a\s+)?' + _DETAILS_PRODUCT, re.I)
_DETAILS_USE = re.compile(r'\b(?:we|I|they|our\s+(?:app|application|service))\s+(?:currently\s+)?(?:call|calls|request|requests|make|makes)\s+(?:(?:a|the|our)\s+)?(?:final\s+)?' + _DETAILS_PRODUCT, re.I)
_DETAILS_NONE = re.compile(r"\b(?:do not|don't|does not|doesn't|never|will not|won't)\s+(?:call|request|use|make)\s+(?:any\s+|a\s+)?Place\s+Details\b(?!\s+(?:Essentials|Pro|Enterprise)\b)", re.I)
_TRAVEL_MODE = re.compile(r'\b(?P<mode>driving|walking|cycling|bicycling|two[- ]wheeler|motorcycle|truck|transit)\s+(?:routes?|routing|directions|matri(?:x|ces))\b', re.I)


def storage_requirements(clause, *, requested=False):
    """Read stated storage polarity while preserving quantities and result types."""
    positive, negative = _ASSERTIONS['storage_required']
    matches = [(polarity, match) for polarity, pattern in ((True, positive), (False, negative))
               for match in re.finditer(pattern, clause, re.I)]
    matches.extend((False, match) for match in re.finditer(
        r'\b(?:no|without)\s+(?:(?:result|response|address|permanent|long[- ]term)\s+)?(?:storage|retention|caching)\b', clause, re.I))
    if requested:
        matches.extend((True, match) for match in re.finditer(r'\b(?:for|with|when|if|assuming)\s+' + _STORAGE, clause, re.I))
        matches.extend((True, match) for match in re.finditer(r'\bwith\s+(?:(?:result|response|address|permanent|long[- ]term)\s+)?(?:storage|retention|caching)\b', clause, re.I))
    else:
        matches.extend((True, match) for match in re.finditer(
            r'\b(?:we|I|they|our\s+(?:app|application|service))\s+(?:are\s+|currently\s+)?' + _STORAGE, clause, re.I))
        matches.extend((True, match) for match in re.finditer(
            _STORAGE_OBJECT + r'\s+(?:must|will|need to)\s+be\s+(?:stored|retained|cached|saved)\b', clause, re.I))
    for polarity, match in sorted(matches, key=lambda item: item[1].start()):
        if _asserted(clause, match, negative=not polarity):
            yield polarity, match


def details_requirements(clause):
    """A terminating Details product establishes completion and, when named, its SKU."""
    for pattern in (_DETAILS_END, _DETAILS_USE):
        for match in pattern.finditer(clause):
            if not _asserted(clause, match):
                continue
            yield 'details_completion', True, match
            product = ' '.join(match['product'].split())
            if re.search(r'\b(?:Essentials|Pro|Enterprise)\b', product, re.I):
                yield 'details_sku', product, match
    for match in _DETAILS_NONE.finditer(clause):
        yield 'details_completion', False, match


def travel_requirements(clause):
    for match in _TRAVEL_MODE.finditer(clause):
        mode = match['mode'].casefold().replace(' ', '-')
        yield 'cycling' if mode == 'bicycling' else mode, match


def customer_texts(enquiry):
    return [(f'history[{i}]', turn['text']) for i, turn in enumerate(enquiry.get('history', []))
            if turn['role'] == 'user'] + [('query', enquiry['query'])]


_BOUNDARY = re.compile(r"[.!?;\n]|,(?!\d)|\b(?:but|however|whereas|while)\b|\band\b(?!\s+without\b)", re.I)
_UNCERTAIN = re.compile(r"\b(?:may|might|could|maybe|possibly|perhaps|optional(?:ly)?|whether|if)\b", re.I)
_QUESTION = re.compile(r"^\s*(?:what|which|do|does|should|would|can|could|is|are)\b", re.I)
_DOCS = re.compile(r"\b(?:docs?|documentation|pricing page|manual)\b|\b(?:provider|API|service|product)\s+(?:supports?|allows?|limits?|accepts?|requires?|says?|can)\b|\b(?:supports?|allows?|accepts?|permits?|handles?)\b", re.I)
_CUSTOMER = re.compile(r"\b(?:we|they|I|customer|prospect|app)\s+(?:only\s+)?(?:need|needs|want|wants|require|requires|accept|accepts|must|plan)\b", re.I)


def clauses(text):
    start = 0
    for boundary in _BOUNDARY.finditer(text):
        sentence = max(text.rfind(c, 0, start) for c in '.!?;\n') + 1
        conditional = re.search(r'\b(?:if|assuming|suppose|hypothetically)\b', text[sentence:start], re.I)
        yield start, text[start:boundary.start()], 'conditional' if conditional else boundary.group()
        start = boundary.end()
    sentence = max(text.rfind(c, 0, start) for c in '.!?;\n') + 1
    conditional = re.search(r'\b(?:if|assuming|suppose|hypothetically)\b', text[sentence:start], re.I)
    yield start, text[start:], 'conditional' if conditional else ''


def _customer_clause(clause, ending=''):
    if ending in {'?', 'conditional'} or _UNCERTAIN.search(clause) or _QUESTION.search(clause):
        return False
    if _DOCS.search(clause):
        # A stated customer need may mention an API capability, but documentation is not a need.
        if re.search(r'\b(?:docs?|documentation|pricing page|manual)\b', clause, re.I) or not _CUSTOMER.search(clause):
            return False
    return True


def _asserted(clause, match, *, negative=False):
    prefix = clause[:match.start()]
    return negative or not re.search(r"\b(?:not|never|without|don't|doesn't|won't)\b", prefix, re.I)


def route_counts(text):
    """A daily business total or published provider limit is not a route requirement."""
    for offset, clause, ending in clauses(text):
        if not _customer_clause(clause, ending):
            continue
        for pattern in _ROUTE_COUNTS:
            for match in pattern.finditer(clause):
                if _asserted(clause, match):
                    yield offset, match


def requirement_evidence(enquiry, evidence):
    """Validate a quoted excerpt against its enclosing customer assertion."""
    excerpt = evidence.strip().rstrip('.?!;\n').strip()
    if not excerpt:
        return None
    for source, text in reversed(customer_texts(enquiry)):
        if evidence not in text:
            continue
        for _, clause, ending in clauses(text):
            if excerpt in clause and _customer_clause(clause, ending):
                return source, clause
    return None


def extract_requirements(enquiry):
    from .matrix_facts import extract_matrix_facts

    facts = {}
    for source, text in customer_texts(enquiry):
        def add(field, value, match, offset):
            facts[field] = {'field': field, 'value': value, 'source': source,
                            'evidence': match.group(), 'start': offset + match.start(), 'end': offset + match.end()}

        for offset, clause, ending in clauses(text):
            if not _customer_clause(clause, ending):
                continue
            for field, (positive, negative) in _ASSERTIONS.items():
                if field == 'storage_required':
                    continue
                matches = [(match, polarity) for polarity, pattern in ((True, positive), (False, negative))
                           for match in re.finditer(pattern, clause, re.I)]
                for match, polarity in sorted(matches, key=lambda item: item[0].start()):
                    if _asserted(clause, match, negative=not polarity):
                        add(field, polarity, match, offset)
            scenario_command = re.match(r'^\s*(?:please\s+)?(?:compare|estimate|calculate|quote|price)\b', clause, re.I)
            if not scenario_command:
                for value, match in storage_requirements(clause):
                    add('storage_required', value, match, offset)
                for field, value, match in details_requirements(clause):
                    add(field, value, match, offset)
                for value, match in travel_requirements(clause):
                    if _asserted(clause, match) and re.search(
                        r'\b(?:we|I|they|our\s+(?:app|application|service))\s+(?:(?:need|want|require|use|plan|uses|needs|wants|requires)\s+)[^.?!;\n]{0,40}$',
                        clause[:match.start()], re.I,
                    ):
                        add('travel_mode', value, match, offset)
            for match in re.finditer(r'\bwith\s+and\s+without\s+(?:live\s+)?traffic\b', clause, re.I):
                add('traffic_scope', 'with_and_without', match, offset)
        for offset, match in route_counts(text):
            add('max_stops', match.group('value'), match, offset)
    for fact in extract_matrix_facts(enquiry):
        facts[fact['field']] = fact
    return list(facts.values())


def route_count_proposal(value, evidence):
    normalized = lambda text: re.sub(r'\s+', '', str(text)).replace('–', '-')
    return any(normalized(match.group('value')) == normalized(value) for _, match in route_counts(evidence))
