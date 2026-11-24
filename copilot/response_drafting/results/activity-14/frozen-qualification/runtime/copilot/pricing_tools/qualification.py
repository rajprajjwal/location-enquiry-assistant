"""Declare customer geography needed to qualify a regional price comparison."""
import re

from .pricing_intent import regex_hints


_END = (r"(?=\s+(?:but|while|with|for|because|where|which|costs?|priced|supports?|is|are|has|have)\b|"
        r"\s+and\s+(?:we|our|the|this|their|billing|primary|usage|operating|requests?|lookups?|calls?|matrices|routes?|sessions?)\b|[\n.;,!?]|$)")
_PLACE = r"([^\n.;,!?]+?)" + _END
_BILLING = re.compile(
    r"\b(?:billing account(?: country)?|billing country)\s*(?:(?:is\s+)?based in\b|(?:is\s+)?in\b|is\b|[:=])\s*"
    + _PLACE, re.I,
)
_USAGE = re.compile(
    r"\b(?:primary usage(?: geography)?|usage geography|operating region)\s*(?:(?:is\s+)?in\b|is\b|[:=])\s*"
    + _PLACE, re.I,
)
_WORKLOAD_USAGE = re.compile(
    r"\b(?:requests?|lookups?|calls?|matrices|routes?|sessions?)\b\s*"
    r"(?:(?:,\s*)?(?:[\d,]+\s+)?(?:per\s+|a\s+|/\s*)(?:month|day|year|hour|minute|second)\b\s*)?"
    r"in\s+" + _PLACE, re.I,
)
_OPERATING_USAGE = re.compile(
    r"\b(?:our|the|this|their)\s+(?:app|application|service|platform|API|workload)\s+"
    r"(?:(?:will|does)\s+)?(?:operate[sd]?|run[s]?|(?:is|will be)\s+used)\s+in\s+" + _PLACE,
    re.I,
)
_API_USAGE = re.compile(
    r"\b(?:we|our (?:app|application|service|platform))\s+(?:(?:will|currently)\s+)?use[s]?\s+"
    r"[^\n.;,!?]{0,70}?\b(?:API|autocomplete|directions|routing|geocoding|distance matrix)\s+in\s+" + _PLACE,
    re.I,
)
_UNCERTAIN = re.compile(r"\b(?:not|never|no|may|might|possibly|maybe|hypothetically|assuming|suppose|if|unsure|undecided|unknown|unspecified|or)\b", re.I)
_QUESTION_START = re.compile(r"^\s*(?:what if|could|would|can|should|is|are|does|do)\b", re.I)


def _asserted_place(text, match):
    value = match.group(1).strip()
    if not value or len(value) > 80 or not re.fullmatch(r"[A-Za-z][A-Za-z -]*", value):
        return None
    start = max(text.rfind(boundary, 0, match.start()) for boundary in '.;!?\n') + 1
    sentence = text[start:match.end()]
    if re.search(r'\b(?:if|assuming|suppose|hypothetically)\b', sentence, re.I):
        return None
    prefix = text[start:match.start()]
    joins = list(re.finditer(r'\b(?:and|but|while)\b', prefix, re.I))
    if joins:
        start += joins[-1].end()
    clause = text[start:match.end()]
    quoted = re.search(r'\b(?:documentation|pricing guide|docs?|manual)\b.{0,50}\b(?:says?|states?|shows?|mentions?|indicates?|describes?)\b', clause, re.I)
    capability = re.search(r'\b(?:supports?|allows?|permits?|offers?)\b', clause, re.I)
    if _UNCERTAIN.search(clause) or _QUESTION_START.search(clause) or quoted or capability:
        return None
    return value


def explicit_geographies(text):
    patterns = (("billing_country", _BILLING), ("usage_geography", _USAGE),
                ("usage_geography", _WORKLOAD_USAGE), ("usage_geography", _OPERATING_USAGE),
                ("usage_geography", _API_USAGE))
    found = []
    for field, pattern in patterns:
        for match in pattern.finditer(text):
            if (value := _asserted_place(text, match)) is not None:
                found.append({"field": field, "value": value, "source": "query",
                              "evidence": match.group(), "start": match.start(), "end": match.end()})
    # Customer corrections later in the text take precedence in shared state.
    yield from sorted(found, key=lambda fact: fact['start'])


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
