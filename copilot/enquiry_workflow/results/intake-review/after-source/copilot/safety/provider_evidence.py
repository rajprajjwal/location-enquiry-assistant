"""Keep mentioned providers separate from evidenced current service use."""
import re

from mapping.map_gt import CURRENT_PROVIDER_CUES, _canon_provider
from copilot.rag.document_retrieval.query_analyzer import PROVIDER_KEYWORDS, detect


def provider_mentions(text):
    """Return all recognized names in text order, with exact evidence offsets."""
    names = set(detect(text)['providers'])
    hits = []
    for provider, patterns in PROVIDER_KEYWORDS.items():
        if provider not in names:
            continue
        for pattern in patterns:
            for match in re.finditer(r'(?<!\w)(?:' + pattern + r')(?!\w)', text, re.I):
                if provider == 'HERE' and not (match.group() == 'HERE' or re.match(
                    r'here\s+(?:maps|platform|routing|geocoding|technologies|api)\b', text[match.start():], re.I
                )):
                    continue
                hits.append({'value': provider, 'evidence': match.group(),
                             'start': match.start(), 'end': match.end()})
    unique = {}
    for hit in sorted(hits, key=lambda item: (item['start'], -item['end'])):
        unique.setdefault(hit['value'], hit)
    return list(unique.values())


def _asserted(text, match):
    prefix = re.split(r'[.!?;\n]|\b(?:but|however|whereas)\b', text[:match.start()], flags=re.I)[-1]
    before_name = match.group()[:match.start('prov') - match.start()]
    scope = prefix + before_name
    if re.search(r'\b(?:documentation|docs|manual|example)\b', scope, re.I):
        return False
    if re.match(r'our\b', match.group(), re.I):
        return not re.search(r"\b(?:not|never|proposed|planned|future|will|may|might|if|suppose|assuming|hypothetically)\b|\bplan(?:ning)?\s+to\b|n't\b", scope, re.I)
    if re.search(r"\b(?:if|whether|assuming|suppose|hypothetically|can|could|should|would|shall|may|might|will|do|does|did|not|never|no longer|used to)\b|n't\b", scope, re.I):
        return False
    # A completed migration does not establish that its source is still current.
    return not re.match(r'(?:migrated|switched|moved)\b', match.group(), re.I)


def _current_provider_hits(text):
    hits = []
    patterns = [pattern for _, pattern in CURRENT_PROVIDER_CUES]
    name = (r"(?P<prov>Google(?:\s+Maps(?:\s+Platform)?)?|Mapbox|Ola(?:\s+Maps)?|HERE(?:\s+Maps)?|"
            r"Mappls(?:\s*\(MapmyIndia\))?|MapmyIndia|OSRM|OSM\s+Nominatim|Nominatim|OpenStreetMap|OSM)\b")
    patterns.extend(re.compile(prefix + name, re.I) for prefix in (
        r"\b(?:we|I)\s+(?:(?:now|currently|actually)\s+)?(?:use|am using|are using)\s+(?:the\s+)?",
        r"\bour\s+(?:\d+\s*[x×]\s*\d+\s+)?",
        r"\b(?:we|I)\s+(?:switched|moved|migrated)\s+(?:from\s+[^.!?;\n]{1,80}?\s+)?to\s+",
        r"\b(?:I(?:'m| am)|we(?:'re| are))\s+setting\s+up\s+",
    ))
    mentions = provider_mentions(text)
    for pattern in patterns:
        for match in pattern.finditer(text):
            if not _asserted(text, match):
                continue
            canonical = _canon_provider(match.group('prov'))
            if canonical is None:
                continue
            # "We use X and Y" is not evidence for a single current provider.
            following = [item for item in mentions if item['start'] >= match.end('prov')]
            if following and re.fullmatch(r"\s*(?:(?:for|with)\s+[\w -]+\s+)?(?:and|or|/|&)\s*", text[match.end('prov'):following[0]['start']], re.I):
                return []
            hits.append({'value': canonical, 'span': match.group('prov'),
                         'evidence': match.group(), 'start': match.start(), 'end': match.end()})
    return hits


def _operational_hit(text):
    for match in re.finditer(r'[^.!?;\n]+', text):
        clause = match.group()
        if re.search(r'\b(?:if|suppose|assuming|hypothetically|docs?|documentation|example|may|might|could|would)\b', clause, re.I):
            continue
        if re.match(r'\s*["\u201c]?(?:what|which|how|do|does|can|should|is|are)\b', clause, re.I):
            continue
        owned = re.search(r"\b(?:our|my|we)\b|\b(?:looping|calling|sending)\b", clause, re.I)
        observed = re.search(r'\b(?:fails?|failing|returns?|returned|gives?|says|REQUEST_DENIED|OVER_QUERY_LIMIT|ZERO_RESULTS|[45]\d\d)\b', clause, re.I)
        names = provider_mentions(clause)
        if owned and observed and len(names) == 1:
            return {'value': names[0]['value'], 'span': names[0]['evidence'],
                    'evidence': clause.strip(), 'start': match.start() + len(clause) - len(clause.lstrip()),
                    'end': match.end() - len(clause) + len(clause.rstrip())}
    return None


def provider_retractions(text):
    """Negative current-use assertions revoke only the named provider."""
    revoked = []
    for mention in provider_mentions(text):
        prefix = re.split(r'[.!?;\n]', text[:mention['start']])[-1]
        if re.search(r"\b(?:we|I)\s+(?:(?:are|am)\s+)?(?:no longer\s+(?:use|using)|(?:do not|don't|never)\s+use|used\s+to\s+use|stopped\s+using)\s+(?:the\s+)?$", prefix, re.I):
            revoked.append(mention['value'])
    return revoked


def ambiguous_current_providers(text):
    """Two explicitly current alternatives cannot fit the scalar current-provider field."""
    hits = _current_provider_hits(text)
    if len({hit['value'] for hit in hits}) > 1:
        return True
    if len(provider_mentions(text)) < 2:
        return False
    # Coordinated uses share the same affirmative verb.
    joined = re.search(r"\b(?:we|I)\s+(?:(?:now|currently)\s+)?use\s+(?P<prov>Google|Mapbox|Ola|HERE|Mappls|OSRM|Nominatim)\b[^.!?;\n]+\b(?:and|or)\s+(?:Google|Mapbox|Ola|HERE|Mappls|OSRM|Nominatim)\b", text, re.I)
    return bool(joined and _asserted(text, joined)
                and not re.search(r'\b(?:consider|compare|evaluat|recommend|switch|migrat)\w*\b', text, re.I))


def current_provider_hit(text):
    """Admit evidenced current use, never a comparison, future option or bare name."""
    if ambiguous_current_providers(text):
        return None
    hits = _current_provider_hits(text)
    if len({hit['value'] for hit in hits}) == 1:
        hit = min(hits, key=lambda item: item['start'])
    else:
        hit = _operational_hit(text)
    return hit if hit and _canon_provider(hit['value']) and hit['value'] not in provider_retractions(text) else None


def current_provider_revoked(enquiry, provider, *, trusted_confirmation=False):
    """Replay retractions without letting a comparison erase a confirmed provider."""
    sources = [turn['text'] for turn in enquiry.get('history', []) if turn['role'] == 'user']
    sources.append(enquiry['query'])
    confirmed = revoked = -1
    for index, text in enumerate(sources):
        hit = current_provider_hit(text)
        if hit and hit['value'] == provider:
            confirmed = index
        if trusted_confirmation:
            names = provider_mentions(text)
            if len(names) == 1 and names[0]['value'] == provider and re.fullmatch(
                r'\s*' + re.escape(names[0]['evidence']) + r'(?:\s+Maps(?:\s+Platform)?)?[.!]?\s*', text, re.I
            ):
                confirmed = index
        if ambiguous_current_providers(text) or provider in provider_retractions(text):
            revoked = index
    return revoked > confirmed
