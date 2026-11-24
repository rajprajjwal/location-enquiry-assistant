"""Resolve product evidence for quotes and one-request matrix comparisons."""
import re

from .answers import make_draft

_GOOGLE = "https://developers.google.com/maps"
_MAPBOX = "https://docs.mapbox.com/api"
_OSM_POLICY = "https://operations.osmfoundation.org/policies/nominatim/"
_REFERENCES = {
    "directions_products": {
        "directions_legacy": (_GOOGLE + "/documentation/directions/get-directions",
            r"Directions API \(Legacy\) can no longer be enabled for new Google Cloud projects\. Existing projects remain fully supported\."),
        "routes_skus": (_GOOGLE + "/documentation/routes/usage-and-billing",
            r"Enterprise\s*:\s*Billed for requests that use an enterprise feature, such as two-wheel routing or large vehicle routing\."),
        "mapbox_directions": (_MAPBOX + "/navigation/directions/",
            r"Requests using the driving , driving-traffic , walking , and cycling profiles can specify up to \d+ total waypoints[^\n]+"),
    },
    "matrix_limits": {
        "legacy_project": (_GOOGLE + "/documentation/distance-matrix/distance-matrix",
            r"Distance Matrix API \(Legacy\) can no longer be enabled for new Google Cloud projects\. Existing projects remain fully supported\."),
        "legacy_limit": (_GOOGLE + "/documentation/distance-matrix/usage-and-billing",
            r"Maximum of (\d+) origins or \d+ destinations per request\.[\s\S]{0,130}?Maximum (\d+) elements per server-side request\."),
        "routes_limit": (_GOOGLE + "/documentation/routes/compute_route_matrix",
            r"The number of elements cannot exceed (\d+) for routes that are not TRANSIT routes\.[\s\S]{0,1200}?If you specify origins or destinations using address or place ID , you specify up to (\d+) total this way\."),
        "mapbox_limit": (_MAPBOX + "/navigation/matrix/",
            r"For the mapbox/driving , mapbox/walking , and mapbox/cycling profiles:[\s\S]{0,180}?Maximum (\d+) input coordinates per request"),
        "ola_limit": ("https://maps.olakrutrim.com/openapi/ola-maps-apis-oas.yaml",
            r"the response includes `x × y` origin–destination pairs, with a maximum of \*\*(\d+)\*\* pairs per request"),
        "mappls_limit": ("https://developer.mappls.com/documentation/sdk/rest-apis/mappls-distance-matrix-api/readme",
            r"maximum number of points are limited to (\d+) only including source and secondary positions\."),
        "mappls_many": ("https://developer.mappls.com/documentation/sdk/rest-apis/mappls-distance-matrix-api/readme",
            r"To specify which of the coordinates supplied in the URL are to be treated as source position for many to many distance matrix calculation, indicate that coordinate pair's index\."),
    },
    "reverse_geocoding_policy": {
        "google_storage": (_GOOGLE + "/documentation/geocoding/policies",
            r"Cache or store Google Maps Content only as expressly permitted under the Google Maps Platform Service Specific Terms"),
        "mapbox_storage": (_MAPBOX + "/search/geocoding/",
            r"Temporary results are not allowed to be cached, while Permanent results are allowed to be cached and stored indefinitely\."),
        "public_rate": (_OSM_POLICY, r"an absolute maximum of 1 request per second"),
        "public_grid": (_OSM_POLICY, r"Systematic queries This includes reverse queries in a grid[^\n]+"),
        "public_tracking": (_OSM_POLICY, r"Applications and services whose primary function is related to geocoding must run their own service\. This includes but is not limited to package/vehicle tracking applications[^\n]+"),
    },
    "autocomplete_global_price": {
        "autocomplete_sku": (_GOOGLE + "/billing-and-pricing/pricing",
            r"\| Autocomplete Requests(?: [\w-]+)? \| [\d,]+ \| \$[\d.]+[^\n]+"),
    },
}
_GRID = re.compile(r"\b([1-9]\d{0,5})\s*(?:origins?\s*)?[×x]\s*([1-9]\d{0,5})\b", re.I)
_OPTIONS = re.compile(r"\b(?:options?|alternatives?|compare|which [^?.]{0,45}(?:apis?|providers?|services?))\b", re.I)
_PROJECT = re.compile(r"\b(?:projects?|legacy|migrat\w*)\b", re.I)
_MATRIX_FIT = re.compile(
    r"\b(?:accept|fit|support|handle|allow|cap|limit|maximum|split)\w*\b", re.I,
)
_SINGLE_REQUEST = re.compile(r"\b(?:one|single|each|per|one single) (?:api )?(?:call|request)\b", re.I)


def pricing_scope(api, query, latest, history):
    if api == "directions" and (
        re.search(r"\b(?:options?|alternatives?|which [^?.]{0,45}(?:apis?|providers?|services?))\b", query, re.I)
        or _PROJECT.search(query) or (
            query != latest and history and history[-1].get("role") == "assistant"
            and _PROJECT.search(history[-1].get("text", ""))
        )
    ):
        return "directions_products"
    if api == "distance_matrix" and _GRID.search(query):
        return "matrix_limits"
    if api == "reverse_geocode" and (
        _OPTIONS.search(query) or re.search(r"\b(?:stor\w*|cach\w*|persist\w*|retai\w*)\b", query, re.I)
    ):
        return "reverse_geocoding_policy"
    if api == "autocomplete" and query != latest and re.search(r"\bSKU\b", latest, re.I) and re.search(
        r"\b(?:new|legacy)\b", latest, re.I,
    ) and re.search(r"\bglobal (?:list[- ]?)?(?:price|pricing|rate)\b", query, re.I):
        return "autocomplete_global_price"
    return None


def matrix_shape(query):
    match = _GRID.search(query)
    if match and "matrix" in query.casefold() and _MATRIX_FIT.search(query) and _SINGLE_REQUEST.search(query):
        return int(match[1]), int(match[2])
    return None


def reference_hits(scope, sources, *, url_key, text_key):
    matches = {}
    for name, (url, pattern) in _REFERENCES[scope].items():
        for hit in sources:
            if hit[url_key].rstrip("/") != url.rstrip("/"):
                continue
            match = re.search(pattern, hit[text_key], re.I)
            if match:
                matches[name] = (hit, match)
                break
    return matches


def _citation(hit, match, claim=None):
    return {"url": hit["source_url"], "span": match[0], "supports_claim": claim or match[0],
            "quote_or_summary": "summary" if claim else "verbatim"}


def add_pricing_evidence(result, scope, passages):
    draft, comparison = result["draft"], result["comparison"]
    matches = reference_hits(scope, passages, url_key="source_url", text_key="relevant_passage")
    if scope == "matrix_limits":
        keys = ("legacy_project", "legacy_limit", "routes_limit")
    elif scope == "autocomplete_global_price":
        keys = ()
    else:
        keys = matches.keys()
    citations = list(draft["citations"])
    seen = {(cite["url"], cite["span"]) for cite in citations}
    lines = []
    for key in keys:
        if key not in matches:
            continue
        hit, match = matches[key]
        cite = _citation(hit, match)
        if (cite["url"], cite["span"]) in seen:
            continue
        citations.append(cite)
        seen.add((cite["url"], cite["span"]))
        lines.append(f"- {cite['span']} [{len(citations)}]")
    if not lines and scope == "autocomplete_global_price":
        return result
    note = "Product and policy details" if lines else "Product or policy details could not be verified for this quote."
    text = "\n".join((draft["draft_text"], "", note, *lines))
    urls = list(dict.fromkeys(cite["url"] for cite in citations))
    return {**result, "draft": make_draft(text, citations), "comparison": {**comparison, "source_urls": urls}}


def matrix_comparison(origins, destinations, passages):
    matches = reference_hits("matrix_limits", passages, url_key="source_url", text_key="relevant_passage")
    elements, points = origins * destinations, origins + destinations
    intro = (f"{origins:,} origins × {destinations:,} destinations = {elements:,} elements. "
             f"The request would have {points:,} input points if every origin and destination is distinct.")
    lines, citations, providers = [intro], [], []
    expected = {
        "legacy_limit": ("Google Maps Platform", "Distance Matrix Legacy"),
        "routes_limit": ("Google Maps Platform", "Compute Route Matrix"),
        "mapbox_limit": ("Mapbox", "Matrix"),
        "ola_limit": ("Ola Maps", "Distance Matrix"),
        "mappls_limit": ("Mappls (MapmyIndia)", "Distance Matrix"),
    }
    for key, (provider, product) in expected.items():
        label = f"{provider} {product}"
        if key not in matches or key == "mappls_limit" and "mappls_many" not in matches:
            lines.append(f"- {label}: one-call fit is unverified.")
            continue
        hit, match = matches[key]
        caps = [int(group) for group in match.groups()]
        if key == "legacy_limit":
            axis, cap = caps
            fits = max(origins, destinations) <= axis and elements <= cap
            detail = f"{axis} origins or destinations and {cap} elements per request"
        elif key == "routes_limit":
            cap, address_cap = caps
            fits = elements <= cap
            detail = f"{cap} elements for standard non-transit requests, subject to mode and the {address_cap}-point address/place ID cap"
        elif key == "ola_limit":
            fits = elements <= caps[0]
            detail = f"{caps[0]} origin–destination pairs per request"
        else:
            fits = points <= caps[0]
            detail = f"{caps[0]} input points per request"
        if not fits and key in {"mapbox_limit", "mappls_limit"}:
            verdict = "exceeds the cap if the inputs are distinct"
        elif key == "routes_limit" and fits:
            verdict = "fits the standard element cap; verify the routing mode and input format"
        else:
            verdict = "fits the documented cap" if fits else "exceeds the documented cap"
        claim = f"{label}: {verdict} ({detail})."
        citations.append(_citation(hit, match, claim))
        refs = f"[{len(citations)}]"
        if key == "mappls_limit":
            citations.append(_citation(*matches["mappls_many"]))
            refs += f" [{len(citations)}]"
        lines.append(f"- {claim} {refs}")
        providers.append(provider)
    if not citations:
        return {"draft": None, "comparison": None, "pricing_source_hits": []}
    return {
        "draft": make_draft("\n\n".join(lines), citations),
        "comparison": {"applicable": True, "providers": list(dict.fromkeys(providers)), "dimensions": ["limits"],
                       "assumptions": ["Input point count assumes distinct origins and destinations."],
                       "source_urls": list(dict.fromkeys(cite["url"] for cite in citations))},
        "pricing_source_hits": [],
    }
