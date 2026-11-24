"""Resolve the provider for documentation questions."""

import re

from copilot.rag.document_retrieval.query_analyzer import detect

_PROVIDER_REPLIES = {
    "google": "Google Maps Platform", "google maps": "Google Maps Platform",
    "google maps platform": "Google Maps Platform", "mapbox": "Mapbox",
    "ola": "Ola Maps", "ola maps": "Ola Maps", "here": "HERE", "here maps": "HERE",
    "osrm": "OSRM", "nominatim": "OSM Nominatim", "osm nominatim": "OSM Nominatim",
    "mappls": "Mappls (MapmyIndia)", "mapmyindia": "Mappls (MapmyIndia)",
}


def provider_reply(text: str) -> str | None:
    reply = re.sub(r"^(?:we use|i use|we're using|i'm using)\s+", "", text.strip().lower())
    return _PROVIDER_REPLIES.get(reply.rstrip(".!").strip())


def resolve_provider(query: str, history: list[dict]) -> str | None:
    providers = detect(query)["providers"]
    if providers:
        return providers[0] if len(providers) == 1 else None
    for turn in reversed(history):
        if turn["role"] == "user":
            providers = detect(turn["text"])["providers"]
            if providers:
                return providers[0] if len(providers) == 1 else None
    return None


def bind_confirmed_provider(interpretation, provider):
    """Apply a recognized active reply after interpretation merges older history."""
    from copilot.enquiry_interpretation import seam

    if provider not in seam.load_vocab().providers:
        return interpretation
    payload = interpretation.model_dump(mode="json")
    qualification = payload["qualification_details"]
    qualification["current_provider"] = provider
    missing = list(seam.compute_missing_required_fields(qualification))
    qualification.update(missing_required_fields=missing, complete=not missing)
    payload["missing_required_fields"] = missing
    payload["field_provenance"]["current_provider"] = "rule"
    return type(interpretation).model_validate(payload)
