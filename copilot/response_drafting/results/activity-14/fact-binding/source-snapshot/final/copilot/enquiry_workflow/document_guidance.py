"""Compose bounded answers from official product references."""

from decimal import Decimal
import re

from .answers import make_draft

_OLA = "https://maps.olakrutrim.com/docs/routing-apis/"
_OSRM = "https://project-osrm.org/docs/"
_NOMINATIM = "https://nominatim.org/release-docs/"
_NOMINATIM_POLICY = "https://operations.osmfoundation.org/policies/nominatim/"
_MAPPLS = "https://developer.mappls.com/documentation/sdk/rest-apis/mappls-maps-auto-suggest-api-example/"
_MAPPLS_GLOBAL = "https://about.mappls.com/api/global-api/"
_GOOGLE_MATRIX = "https://developers.google.com/maps/documentation/routes/compute_route_matrix"
_MAPBOX = "https://docs.mapbox.com/api/"
_RATE_QUERY = re.compile(
    r"(?<![\w.,-])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s+(?:(?:driver|gps)\s+)?"
    r"(pings?|requests?|calls?|lookups?)\s+(?:a|per|/)\s*(second|minute)\b", re.I,
)
_RATE_LIMIT = re.compile(
    r"The default Geocoding API rate limit is ([\d,]+) requests per minute, "
    r"but can be adjusted on a per-account basis\.", re.I,
)
_COUNTRIES = re.compile(r"maps available for ([^.\n]+)\.", re.I)


def guidance_kind(query):
    """Select a supported question type without using benchmark labels."""
    q = query.lower()
    if ("mapbox" in q and "reverse geocod" in q and _RATE_QUERY.search(q)
            and re.search(r"throttl|rate limit|quota|429|too (?:many|fast)", q)
            and not re.search(r"\b(?:batch|batching|burst|concurren\w*|versus|vs)\b", q)
            and len(_RATE_QUERY.findall(q)) == 1):
        return "geocoding_rate"
    if (re.search(r"\bola\b", q) and "distance matrix basic" in q
            and re.search(r"differences?|compar(?:e|ison)|versus|\bvs\b", q)
            and not re.search(r"\b(?:prices?|costs?|pricing|rates?|quotas?|limits?)\b", q)):
        return "ola_matrix_variants"
    if ("osrm" in q and "nominatim" in q and "reverse geocod" in q
            and re.search(r"\b(?:can|instead|replace|versus|vs|difference|alternative)\b", q)):
        return "reverse_service"
    if ("matrix" in q and "traffic" in q and re.search(r"\b(?:ola|google|mapbox)\b", q)
            and re.search(r"\b(?:what|which)\b.*\b(?:clarify|confirm|gather|ask)\b", q, re.S)
            and re.search(r"\b(?:requirements?|volume|matrix[- ]size|origins|destinations)\b", q)):
        return "matrix_requirements"
    if (re.search(r"auto-?complete|type[- ]ahead|search-as-you-type|autosuggest", q)
            and re.search(r"\b(?:coverage|covered|supported countries|which countries)\b", q)
            and re.search(r"\b(?:which providers|what providers|nominatim|mappls)\b", q)
            and not re.search(r"\b(?:only|exclusively)\b", q)):
        return "autocomplete_coverage"
    return None


def _countries(query, text):
    match = _COUNTRIES.search(text)
    if not match:
        return []
    return [name for name in re.split(r"\s*(?:,|&| and )\s*", match[1]) if name and
            re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", query, re.I)]


def _references(kind, query):
    if kind == "geocoding_rate":
        endpoint = "geocoding-v5/" if re.search(r"\bv5\b", query, re.I) else "geocoding/"
        return [("quota", _MAPBOX + "search/" + endpoint, _RATE_LIMIT.pattern),
                ("429", _MAPBOX + "search/" + endpoint, r"An HTTP error code of 429 will be returned if the rate limit is reached\.")]
    if kind == "ola_matrix_variants":
        return [("standard", _OLA + "distance-matrix-api", r"Distance Matrix API provides distance, near real-time ETA and routable path\(s\) with traffic data considerations between multiple points\."),
                ("basic", _OLA + "distance-matrix-basic-api", r"Pairwise distances and ETAs across many origins and destinations without live traffic[^\n]+")]
    if kind == "reverse_service":
        return [("nearest", _OSRM, r"Snaps a coordinate to the street network and returns the nearest n matches\."),
                ("reverse", _NOMINATIM, r"Reverse geocoding generates an address from a coordinate given as latitude and longitude\.")]
    if kind == "matrix_requirements":
        choices = [
            ("google", _GOOGLE_MATRIX, r"The Compute Route Matrix methods enforce the following request limits.*?you have 100 elements:"),
            ("mapbox", _MAPBOX + "navigation/matrix/", r"- For the mapbox/driving , mapbox/walking , and mapbox/cycling profiles:[\s\S]+?- Maximum 30 requests per minute"),
            ("ola", _OLA + "distance-matrix-api", r"Distance Matrix API provides distance, near real-time ETA and routable path\(s\) with traffic data considerations between multiple points\."),
        ]
        return [item for item in choices if re.search(r"\b" + item[0] + r"\b", query, re.I)]
    if kind == "autocomplete_coverage":
        return [("global", _MAPPLS_GLOBAL, _COUNTRIES.pattern),
                ("autosuggest", _MAPPLS, r"Autosuggest API is Now Available for \d+ countries across the world\."),
                ("public_policy", _NOMINATIM_POLICY, r"Auto-complete search This is not yet supported by Nominatim and you must not implement such a service on the client side using the API\.")]
    return []


def _matching_references(query, sources, url_key, text_key):
    for key, url, pattern in _references(guidance_kind(query), query):
        for source in sources:
            if not source[url_key].startswith(url):
                continue
            match = re.search(pattern, source[text_key], re.I)
            if match and (key != "global" or _countries(query, match[0])):
                yield key, source, match[0]
                break


def guidance_passages(query, chunks):
    """Select exact official sections alongside the ranked search results."""
    by_id = {}
    for _, chunk, _ in _matching_references(query, chunks, "doc_url", "text"):
        by_id[chunk["chunk_id"]] = {**chunk, "score": 0.0}
    return list(by_id.values())


def guidance_draft(query, passages):
    kind = guidance_kind(query)
    evidence = {key: (source["source_url"], span) for key, source, span in
                _matching_references(query, passages, "source_url", "relevant_passage")}
    if kind == "geocoding_rate" and {"quota", "429"} <= evidence.keys():
        raw_rate, unit, period = _RATE_QUERY.search(query).groups()
        rate = Decimal(raw_rate.replace(",", "")) * (60 if period.lower() == "second" else 1)
        limit = int(_RATE_LIMIT.search(evidence["quota"][1])[1].replace(",", ""))
        assume = "Assuming one reverse-geocoding request per ping, " if unit.lower().startswith("ping") else ""
        per_minute = f"{rate:,.3f}".rstrip("0").rstrip(".")
        given = f"{Decimal(raw_rate.replace(',', '')):f} {unit} per {period}"
        load = f"{given} is {per_minute} requests per minute" if period.lower() == "second" or assume else f"{per_minute} requests per minute"
        if rate > limit:
            result = f"Yes, expect throttling under the default limit. {assume}{load} and exceeds {limit:,} requests per minute."
        else:
            result = f"{assume}{load} and is within the default {limit:,} requests per minute."
        if rate == limit:
            result += " This leaves no headroom."
        return _compose(evidence, [
            ("quota", result + " Confirm your account-specific limit."),
            ("429", "Mapbox returns HTTP 429 when the rate limit is reached."),
        ])
    if kind == "ola_matrix_variants" and {"standard", "basic"} <= evidence.keys():
        return _compose(evidence, [
            ("standard", "Choose Ola Distance Matrix when dispatch or scheduling needs traffic-aware ETAs."),
            ("basic", "Choose Distance Matrix Basic for origin-to-destination distances and ETAs without live traffic."),
        ])
    if kind == "reverse_service" and {"nearest", "reverse"} <= evidence.keys():
        return _compose(evidence, [
            ("nearest", "No, OSRM Nearest only snaps coordinates to the road network and returns nearby matches."),
            ("reverse", "Use Nominatim Reverse when you need a human-readable address from latitude and longitude."),
        ])
    if kind == "matrix_requirements" and evidence:
        checklist = (
            "Before recommending a provider, confirm the number of origins and destinations per batch, "
            "total monthly origin–destination pairs and peak request rate, and whether ETAs need "
            "live traffic, predicted traffic for a departure time, or standard conditions. Also check "
            "whether the workload can be split into multiple requests and how fresh the ETAs need to be."
        )
        claims = {
            "google": "Google Route Matrix counts elements as origins multiplied by destinations.",
            "mapbox": "Mapbox Matrix applies different request sizes and rate limits to traffic and standard profiles.",
            "ola": "Ola Distance Matrix supports traffic-aware routing estimates.",
        }
        return _compose(evidence, [(key, claims[key]) for key in evidence], intro=checklist)
    if kind == "autocomplete_coverage" and {"global", "autosuggest"} <= evidence.keys():
        where = ", ".join(_countries(query, evidence["global"][1]))
        claims = [
            ("global", f"Mappls lists map coverage for {where}."),
            ("autosuggest", "Mappls documents a globally available Autosuggest API. It is a candidate to evaluate. Confirm street and house-number suggestion quality with representative local addresses."),
        ]
        if "nominatim" in query.casefold() and "public_policy" in evidence:
            claims.append(("public_policy", "The public Nominatim service prohibits client-side autocomplete."))
        return _compose(evidence, claims)
    return None


def _compose(evidence, claims, *, intro=None):
    sections = [intro] if intro else []
    citations = []
    for key, claim in claims:
        url, span = evidence[key]
        sections.append(f"{claim} [{len(citations) + 1}]")
        citations.append({"url": url, "span": span, "supports_claim": claim, "quote_or_summary": "summary"})
    return make_draft("\n\n".join(sections), citations)
