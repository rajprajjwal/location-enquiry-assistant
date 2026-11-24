"""Declare customer geography needed to qualify a regional price comparison."""
import re

from .pricing_intent import regex_hints


_BILLING = re.compile(
    r"\b(?:billing account(?: country)?|billing country)\s*(?:(?:is\s+)?based in\b|(?:is\s+)?in\b|is\b|[:=])\s*"
    r"([^\n.;,]+?)(?=\s+(?:and|but|while|with)\b|[\n.;,]|$)", re.I,
)
_USAGE = re.compile(
    r"\b(?:primary usage(?: geography)?|usage geography|operating region)\s*(?:(?:is\s+)?in\b|is\b|[:=])\s*"
    r"([^\n.;,]+?)(?=\s+(?:and|but|while|with)\b|[\n.;,]|$)", re.I,
)


def explicit_geographies(text):
    for field, pattern in (("billing_country", _BILLING), ("usage_geography", _USAGE)):
        for match in pattern.finditer(text):
            yield {"field": field, "value": match.group(1).strip(), "source": "query",
                   "evidence": match.group(), "start": match.start(), "end": match.end()}


def required_geography_facts(usage):
    # Reuse the calculator's India/global distinction for list-price eligibility.
    if usage and usage.casefold().strip() not in {"india", "in", "ind"}:
        return ["usage_geography"]
    return ["billing_country", "usage_geography"]


def comparison_qualification(query, providers, region):
    applicable = len(set(providers)) >= 2 and "Google Maps Platform" in providers
    explicit_scope = regex_hints(query).get("global_price") or re.search(
        r"\b(?:assume|assuming)\b.{0,45}\b(?:india pricing|india rates|india price list|india pricing eligibility)\b",
        query, re.I,
    )
    if not applicable or explicit_scope:
        return {"applicable": False, "required_facts": []}
    supplied = {fact["field"]: fact["value"] for fact in explicit_geographies(query)}
    usage = supplied.get("usage_geography")
    if usage is None and "billing_country" not in supplied:
        usage = region
    return {
        "applicable": True, "required_facts": required_geography_facts(usage),
        "usage_geography": usage, "providers": list(providers),
        "reason": "Qualify the applicable list-price schedule using billing country and primary usage geography.",
    }
