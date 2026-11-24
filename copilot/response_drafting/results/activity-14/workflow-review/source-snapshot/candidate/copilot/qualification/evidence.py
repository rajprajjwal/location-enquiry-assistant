"""Project retrieved evidence into a bounded, source-preserving planning context."""
import hashlib
import json
import re
from urllib.parse import urlsplit

from copilot.rag.document_retrieval.query_analyzer import detect

_TOPICS = {
    'pricing': r'\b(?:prices?|pricing|costs?|billing|billable|fees?|sku|free tier)\b',
    'workload': r'\b(?:volume|workload|throughput|concurren\w*|requests? per|requests?/|per second|per month)\b',
    'limits': r'\b(?:limits?|maximum|max|quota|caps?|restrictions?)\b',
    'matrix': r'\b(?:matri(?:x|ces)|origins?|destinations?|elements?)\b',
    'traffic': r'\b(?:traffic|departure|arrival time|predicted|historical|live eta)\b',
    'coverage': r'\b(?:coverage|geograph\w*|countr\w*|regions?|territor\w*|global)\b',
    'storage': r'\b(?:stor\w*|retain\w*|retention|cach\w*|licens\w*|redistribut\w*|resell|resale|temporary|permanent)\b',
    'sessions': r'\b(?:sessions?|keystrokes?|debounc\w*|place details|session tokens?)\b',
    'deployment': r'\b(?:self.host\w*|managed|public endpoint|public service|backend|deployment|operat\w*)\b',
    'input': r'\b(?:coordinates?|addresses|place ids?|input|parameters?|request body|request format)\b',
    'languages': r'\b(?:languages?|locali[sz]\w*|translation|voice|spoken|instructions?)\b',
    'diagnostics': r'\b(?:errors?|status|failed|failing|denied|credentials?|authentication|authorization|429|403|401)\b',
}
_TOPICS = {name: re.compile(pattern, re.I) for name, pattern in _TOPICS.items()}
_STOP_WORDS = set('the and for with that this what which should would could before after from into about please need needs want wants have has are our their they can api use using'.split())


def _size(value):
    return len(json.dumps(value, ensure_ascii=True))


def _source_group(passage, url):
    if isinstance(passage.get('provider'), str) and passage['provider'].strip():
        return passage['provider'].strip().casefold()
    host = (urlsplit(url).hostname or '').casefold()
    providers = detect(host)['providers']
    return providers[0].casefold() if len(providers) == 1 else host


def _topics(text):
    return {name for name, pattern in _TOPICS.items() if pattern.search(text)}


def _excerpt(text, topics, words, limit):
    if len(text) <= limit:
        return text.strip()
    anchors = [match.start() for name in topics for match in _TOPICS[name].finditer(text)]
    anchors.extend(match.start() for match in re.finditer(r'[A-Za-z][A-Za-z-]{2,}', text)
                   if match.group().casefold() in words)
    windows = {max(0, min(position - limit // 3, len(text) - limit)) for position in anchors}
    windows.add(0)
    def score(start):
        window = text[start:start + limit]
        present = set(re.findall(r'[a-z][a-z-]{2,}', window.casefold()))
        return len(_topics(window) & topics) * 4 + min(len(present & words), 8), -start
    start = max(windows, key=score)
    return text[start:start + limit].strip()


def _entry(candidate, excerpt):
    return {'source_url': candidate['url'], 'passage': excerpt, 'evidence_id': candidate['id']}


def _fit(candidate, result, excerpt, max_chars):
    """Keep URL/identity whole; only shorten the exact source excerpt."""
    if _size([*result, _entry(candidate, '')]) >= max_chars:
        return None
    low, high = 0, len(excerpt)
    while low < high:
        mid = (low + high + 1) // 2
        if _size([*result, _entry(candidate, excerpt[:mid])]) <= max_chars:
            low = mid
        else:
            high = mid - 1
    text = excerpt[:low].rstrip()
    return _entry(candidate, text) if text else None


def planning_evidence(passages, task, max_passages=6, max_chars=3600):
    """Select diverse planning excerpts without changing retrieval order or scores.

    ``max_chars`` bounds the serialized evidence array, including URLs and identities.
    Native-token admission for the complete prompt remains the model client's check.
    IDs bind the URL and original exact retrieved span, independent of excerpt length.
    """
    if max_passages <= 0 or max_chars <= 2:
        return []
    task_topics = _topics(task)
    words = set(re.findall(r'[a-z][a-z-]{2,}', task.casefold())) - _STOP_WORDS
    candidates = []
    seen = set()
    for rank, passage in enumerate(passages or []):
        if not isinstance(passage, dict):
            continue
        url, text = passage.get('source_url'), passage.get('relevant_passage')
        if not isinstance(url, str) or not isinstance(text, str) or not text.strip():
            continue
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc or (url, text) in seen:
            continue
        seen.add((url, text))
        identity = hashlib.sha256((url + '\n' + text).encode()).hexdigest()[:20]
        candidate = {'url': url, 'text': text, 'id': 'evidence_' + identity,
                     'group': _source_group(passage, url), 'rank': rank}
        if _size([_entry(candidate, text.strip()[:1])]) <= max_chars:
            candidates.append(candidate)
    if not candidates:
        return []
    count = min(max_passages, len(candidates))
    metadata = sum(_size(_entry(candidate, '')) for candidate in candidates[:count])
    allowance = max(1, (max_chars - metadata - count - 1) // count)
    for candidate in candidates:
        candidate['excerpt'] = _excerpt(candidate['text'], task_topics, words, allowance)
        candidate['topics'] = _topics(candidate['excerpt']) & task_topics
    result, groups, topics, emitted = [], set(), set(), set()
    while candidates and len(result) < max_passages:
        unseen = {item['group'] for item in candidates} - groups
        pool = [item for item in candidates if item['group'] in unseen] if unseen and max_passages - len(result) <= len(unseen) else candidates
        def utility(item):
            return (len(item['topics'] - topics) * 4 + (3 if item['group'] not in groups else 0)
                    + 1 / (item['rank'] + 1), -item['rank'])
        chosen = max(pool, key=utility)
        candidates.remove(chosen)
        fitted = _fit(chosen, result, chosen['excerpt'], max_chars)
        if fitted is None or (fitted['source_url'], fitted['passage']) in emitted:
            continue
        result.append(fitted)
        emitted.add((fitted['source_url'], fitted['passage']))
        groups.add(chosen['group'])
        topics.update(_topics(fitted['passage']) & task_topics)
    return result
