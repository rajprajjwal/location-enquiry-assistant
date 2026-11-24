"""Build sourced definitions and deterministic price estimates."""

from functools import lru_cache
import re


_DEFINITION_QUERY = re.compile(
    r"^\s*(?:what (?:is|are)|define|explain)\s+(?:an?\s+|the\s+)?"
    r"(?:directions?|distance matrix|autocomplete|reverse geocod(?:e|ing))(?:\s+(?:api|service))?[\s?.!]*$",
    re.I,
)
_DEFINITIONS = {
    "directions": (
        "a94af10eee9e",
        "Calculate optimal driving, walking, and cycling routes using traffic- and incident-aware routing",
        "A Directions API calculates a route between locations. Depending on the provider and travel mode, it can also return turn-by-turn instructions.",
    ),
    "distance_matrix": (
        "4d342715b5ea",
        "The Google Maps Distance Matrix API calculates travel distance and time between multiple origins and destinations.",
        "A Distance Matrix API calculates travel distances and times for pairs of origins and destinations.",
    ),
    "autocomplete": (
        "5fdf7868f071",
        "The Autocomplete (New) service offers place and query predictions based on user input",
        "An Autocomplete API suggests places or search queries as a user types.",
    ),
    "reverse_geocode": (
        "8e48d374fb76",
        "Reverse Geocoding is a process to give the closest matching address to a provided geographical coordinates (latitude/longitude).",
        "A Reverse Geocoding API takes geographic coordinates and returns a nearby address or place.",
    ),
}


def is_definition(query: str, api: str) -> bool:
    return api in _DEFINITIONS and bool(_DEFINITION_QUERY.fullmatch(query))


@lru_cache(maxsize=1)
def _definition_chunks():
    from copilot.rag.document_indexing.bm25 import load_chunks

    ids = {item[0] for item in _DEFINITIONS.values()}
    return {chunk["chunk_id"]: chunk for chunk in load_chunks() if chunk["chunk_id"] in ids}


def definition(api: str):
    chunk_id, excerpt, answer = _DEFINITIONS[api]
    chunk = _definition_chunks().get(chunk_id)
    if not chunk or excerpt not in chunk["text"]:
        return None
    return make_draft(answer, [{
        "url": chunk["doc_url"], "span": excerpt, "supports_claim": answer, "quote_or_summary": "summary",
    }])


def make_draft(text, citations=()):
    return {"draft_text": text, "citations": list(citations), "is_refusal": False, "refusal": None}


def pricing(query, interpretation, client):
    from copilot.rag.document_retrieval.query_analyzer import detect
    from copilot.pricing_tools.pricing_evidence import lookup
    from copilot.pricing_tools.pricing_intent import render_summary, requests_usd_only, run

    usd_only = requests_usd_only(query)
    result = run(query, client=client)
    named = detect(query)["providers"]
    rows = [row for row in result["results"] if not named or row["provider"] in named]
    groups = {}
    for row in rows:
        groups.setdefault(row["group"], []).append(row)

    verified_rows, citations, evidence, unverified_groups = [], [], [], []
    references = {}
    index_by_id = {}
    for group, items in groups.items():
        supported = [
            lookup(item["sku"], include_fx=item["currency"] != "USD" if usd_only else None)
            for item in items
        ]
        if any(hits is None for hits in supported):
            unverified_groups.append(group)
            continue
        verified_rows.extend(items)
        references[group] = []
        for hits in supported:
            for hit in hits:
                identifier = hit["document_id"]
                if identifier not in index_by_id:
                    index_by_id[identifier] = len(citations)
                    span = hit["relevant_passage"]
                    citations.append({
                        "url": hit["source_url"], "span": span,
                        "supports_claim": span, "quote_or_summary": "verbatim",
                    })
                    evidence.append({**hit, "reference": len(citations), "estimate_groups": []})
                index = index_by_id[identifier]
                reference = index + 1
                if reference not in references[group]:
                    references[group].append(reference)
                    evidence[index]["estimate_groups"].append(group)

    if not verified_rows:
        return None, None, []
    priced = {row["provider"] for row in verified_rows}
    provider_names = list(dict.fromkeys(named or sorted(priced)))
    missing = [provider for provider in provider_names if provider not in priced]
    text = render_summary({**result, "results": verified_rows}, source_refs=references, usd_only=usd_only)
    if unverified_groups:
        text += "\nNo verified estimate for " + "; ".join(unverified_groups) + "."
    if missing:
        text += "\nNo verified estimate for providers: " + ", ".join(missing) + "."
    assumptions = ["Estimates use the bundled vendor list-price snapshot, excluding taxes and negotiated discounts."]
    text += "\n" + assumptions[0]

    from copilot.enquiry_interpretation.seam import load_vocab

    canonical = set(load_vocab().providers)
    providers = [name for name in provider_names if name in canonical]
    qualification = interpretation.model_dump(mode="json")["qualification_details"]
    volume = qualification.get("monthly_volume") or {}
    comparison = {
        "applicable": bool(providers),
        "providers": providers,
        "dimensions": ["pricing"] if providers else [],
        "assumptions": assumptions,
        "source_urls": list(dict.fromkeys(cite["url"] for cite in citations)),
        "equivalent_requirements": {
            "api": interpretation.api,
            "region": qualification.get("region"),
            "monthly_volume_raw": volume.get("raw"),
        },
        "notes": "Some requested estimates could not be verified." if missing or unverified_groups else None,
    }
    return make_draft(text.strip(), citations), comparison, evidence


def documentation_dimension(query, intent):
    if re.search(r"\b(?:coverage|covered|regions?|countries|cities)\b", query, re.I):
        return "coverage"
    if intent == "coverage_limits" or re.search(r"\b(?:limits?|maximum|max|quotas?)\b", query, re.I):
        return "limits"
    return "capabilities"


def provider_query(query, provider):
    from copilot.rag.document_retrieval.query_analyzer import PROVIDER_KEYWORDS

    for other, aliases in PROVIDER_KEYWORDS.items():
        if other != provider:
            for alias in sorted([re.escape(other), *aliases], key=len, reverse=True):
                query = re.sub(alias, " ", query, flags=re.I)
    question = re.sub(r"\b(?:compare|versus|vs)\b", " ", query, flags=re.I)
    return f"{provider} {' '.join(question.split())}"
