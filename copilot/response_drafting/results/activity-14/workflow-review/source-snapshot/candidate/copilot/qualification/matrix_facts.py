"""Bind matrix quantities to their statistic, period and dimension."""
import re

STATISTICS = {
    'typical': 'typical', 'typically': 'typical', 'usual': 'typical', 'normally': 'typical',
    'maximum': 'maximum', 'max': 'maximum', 'at most': 'maximum',
}
COUNT_FIELDS = {'typical_origin_count', 'maximum_origin_count',
                'typical_destination_count', 'maximum_destination_count',
                'matrices_per_hour', 'matrices_per_month'}
_SHAPE = re.compile(r'\b(?P<stat>typical(?:ly)?|usual|normally|maximum|max|at most)\s+'
                    r'(?P<count>\d+)\s+(?P<dimension>origins?|destinations?)\b', re.I)
_REVERSED = re.compile(r'\b(?P<dimension>origins?|destinations?)\s*[:=]?\s*'
                       r'(?P<stat>typical(?:ly)?|usual|normally|maximum|max|at most)\s*[:=]?\s*(?P<count>\d+)\b', re.I)
_PERIOD = re.compile(r'\b(?P<count>\d[\d,]*)\s+matri(?:x|ces)\s*(?:per|/|each|every|an?|a)\s*(?P<period>hour|month)\b', re.I)


def quantities(text):
    for pattern in (_SHAPE, _REVERSED):
        for match in pattern.finditer(text):
            statistic = STATISTICS[match['stat'].casefold()]
            dimension = 'origin' if match['dimension'].casefold().startswith('origin') else 'destination'
            yield f'{statistic}_{dimension}_count', int(match['count']), match
    for match in _PERIOD.finditer(text):
        yield f'matrices_per_{match["period"].lower()}', int(match['count'].replace(',', '')), match


def validates_quantity(field, value, clause):
    if field not in COUNT_FIELDS:
        return True
    try:
        proposed = float(str(value).replace(',', ''))
    except ValueError:
        return False
    return any(field == found and proposed == count for found, count, _ in quantities(clause))


def extract_matrix_facts(enquiry):
    from .extraction import clauses, _customer_clause, customer_texts

    facts = {}
    for source, text in customer_texts(enquiry):
        for offset, clause, ending in clauses(text):
            if not _customer_clause(clause, ending):
                continue
            for field, value, match in quantities(clause):
                facts[field] = {'field': field, 'value': value, 'source': source,
                                'evidence': match.group(), 'start': offset + match.start(), 'end': offset + match.end()}
    return list(facts.values())
