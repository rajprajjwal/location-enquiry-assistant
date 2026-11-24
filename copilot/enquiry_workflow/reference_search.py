"""Find concrete documentation evidence that semantic retrieval can miss."""

import re

from functools import lru_cache

from copilot.rag.document_indexing.bm25 import BM25Index, load_chunks

from .document_guidance import guidance_kind, guidance_passages

_IDENTIFIER = re.compile(r"\b(?:[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+|[A-Za-z]+[a-z][A-Z][A-Za-z]+[A-Za-z0-9]*|[A-Z]{3,}[0-9_]*)\b")
_LIMIT = re.compile(r"\b(?:throttl\w*|rate limits?|requests? per (?:minute|second)|\d[\d,]*\s+(?:\w+\s+){0,3}(?:a|per)\s+(?:second|minute))\b", re.I)
_RATE_HEADING = re.compile(r"\b(?:rate limits?|quotas?|throttl\w*)\b", re.I)
_RATE_VALUE = re.compile(r"\b[\d,]+\s+(?:requests?|calls?|queries|elements)\s+per\s+(?:second|minute|hour)\b", re.I)
_OFFICIAL_TYPES = {"html", "openapi", "markdown", "docs", "official", "reference", "github"}
_NON_IDENTIFIERS = {"API", "SDK", "GPS", "HTTP", "HTTPS", "URL", "JSON", "OSRM", "HERE", "CRM", "ETA", "ETAS", "GET", "POST", "USA", "USD", "INR", "POI", "UUID"}


@lru_cache(maxsize=1)
def _index():
    return BM25Index(load_chunks())


def supplemental_passages(query, providers, existing):
    """Add bounded exact-term and rate-limit evidence from the pinned corpus."""
    if guidance_kind(query):
        guidance = guidance_passages(query, _index().chunks)
        if guidance:
            return guidance
    terms = [word for word in dict.fromkeys(_IDENTIFIER.findall(query)) if word.upper() not in _NON_IDENTIFIERS][:4]
    ids = {hit["chunk_id"] for hit in existing}
    additions = []
    if terms:
        literals = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape,terms)) + r")(?!\w)", re.I)
        additions.extend(_search(f"{' '.join(terms)} {query}", providers, ids, lambda chunk: bool(literals.search(chunk["text"])), 2))
    if _LIMIT.search(query):
        additions.extend(_search(f"{query} rate limits quotas requests per minute requests per second", providers,
                    ids, lambda chunk: bool(_RATE_HEADING.search(chunk.get("section") or "") and _RATE_VALUE.search(chunk["text"])), 2))
    return additions[:2]


def _search(query, providers, seen, useful, limit):
    found = []
    scoped = set(providers)
    for chunk, score in _index().search(query, k=250):
        if chunk["chunk_id"] in seen or chunk.get("kind") not in _OFFICIAL_TYPES:
            continue
        if (scoped and chunk.get("provider") not in scoped) or not useful(chunk):
            continue
        seen.add(chunk["chunk_id"])
        found.append({**chunk, "score": score})
        if len(found) == limit:
            break
    return found
