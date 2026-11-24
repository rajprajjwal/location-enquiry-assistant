"""Build a sourced comparison using one shared workload for all providers."""

from decimal import Decimal
from functools import lru_cache
import re

from .answers import make_draft

DIMENSIONS = ("pricing", "limits", "coverage")
DOCUMENT_DIMENSIONS = ("limits", "coverage")

_API_NAMES = {
    "directions": "Directions",
    "distance_matrix": "Distance Matrix",
    "autocomplete": "Autocomplete",
    "reverse_geocode": "Reverse Geocoding",
}
_DOCUMENT_TOPICS = {
    "limits": "documented request limits, quotas, input and batch limits",
    "coverage": "documented geographic coverage for the requested region",
}
_PRICE = re.compile(r"\b(?:prices?|pricing|costs?|billing|quote|fees?)\b", re.I)
_LIMITS = re.compile(r"\b(?:limits?|quotas?|maximums?|caps?|throttl\w*)\b", re.I)
_COVERAGE = re.compile(r"\b(?:coverage|covered|availability by region|geographic availability)\b", re.I)
_RATE_ASSUMPTION = "Estimates use the bundled vendor list-price snapshot, excluding taxes and negotiated discounts."


def requested(question):
    return all(pattern.search(question) for pattern in (_PRICE, _LIMITS, _COVERAGE))


def named_providers(question):
    from copilot.enquiry_interpretation.seam import load_vocab
    from copilot.rag.document_retrieval.query_analyzer import detect

    canonical = set(load_vocab().providers)
    return [name for name in detect(question)["providers"] if name in canonical]


def monthly_workload(api, question, qualified_volume):
    from mapping.map_gt import extract_monthly_volume
    from copilot.pricing_tools.pricing_intent import regex_hints

    hints = regex_hints(question.lower())
    volume = extract_monthly_volume(question) or qualified_volume or {}
    monthly = bool(volume) or bool(re.search(r"\b(?:month|monthly)\b|/\s*mo\b", question, re.I))
    if api == "distance_matrix" and monthly:
        grid = hints.get("matrix")
        shape = re.search(r"\b(\d+)\s*(?:origins?\s*)?[×x]\s*(\d+)\b", question, re.I)
        calls = volume.get("requests_per_month")
        if not grid and shape and volume.get("unit") in {"calls_per_month", "requests_per_month"}:
            if calls is not None and float(calls).is_integer():
                grid = int(shape[1]), int(shape[2]), int(calls)
        if grid and min(grid) > 0:
            origins, destinations, calls = grid
            return {"quantity": calls, "unit": "matrix_requests", "origins": origins, "destinations": destinations}
    if api == "autocomplete" and monthly:
        if "users_typing" in hints:
            sessions, keystrokes = hints["users_typing"]
            if sessions > 0 and keystrokes > 0:
                return {"quantity": sessions, "unit": "sessions", "keystrokes_per_session": keystrokes}
        sessions = hints.get("sessions")
        if sessions is not None and sessions > 0:
            workload = {"quantity": sessions, "unit": "sessions"}
            if hints.get("ks", 0) > 0:
                workload["keystrokes_per_session"] = hints["ks"]
            return workload
    pairs = re.search(r"\b([\d,]+)\s+(?:origin[- ]destination\s+)?pairs?\s*(?:per month|a month|/month)", question, re.I)
    if api == "distance_matrix" and pairs:
        quantity = int(pairs[1].replace(",", ""))
        return {"quantity": quantity, "unit": "elements"} if quantity > 0 else None
    quantity = volume.get("requests_per_month")
    if quantity is None or quantity < 1 or not float(quantity).is_integer():
        return None
    unit = (volume.get("unit") or "").removesuffix("_per_month")
    if api == "distance_matrix":
        if unit != "elements":
            return None
        unit = "elements"
    elif unit == "sessions" and api == "autocomplete":
        return {"quantity": int(quantity), "unit": "sessions"}
    elif unit not in {"requests", "calls", "lookups", "searches", "queries", "transactions"}:
        return None
    else:
        unit = "requests"
    return {"quantity": int(quantity), "unit": unit}


def _price_input(provider, api, region, workload, question):
    from copilot.pricing_tools.pricing_intent import reconcile, regex_hints

    hints = regex_hints(question.lower())
    # Normalize the shared workload once. Per-provider SKU logic applies its billing unit.
    input_item = reconcile({"provider": provider, "api": api}, {
        key: hints[key] for key in ("traffic", "waypoints", "two_wheeler", "store", "legacy") if key in hints
    })
    quantity = workload["quantity"]
    unit = workload["unit"]
    if unit == "matrix_requests":
        input_item.update(origins=workload["origins"], destinations=workload["destinations"], calls=quantity)
    elif unit == "sessions":
        keystrokes = workload.get("keystrokes_per_session")
        if provider == "Mapbox":
            input_item["sessions"] = quantity
        elif keystrokes:
            input_item["requests"] = quantity * keystrokes
    else:
        input_item["requests"] = quantity
    if provider == "Google Maps Platform":
        input_item["global_price"] = region.casefold().strip() != "india" or bool(hints.get("global_price"))
    return input_item


def _pricing_gap(reason):
    return {"status": "missing_evidence", "estimates": [], "reason": reason}


def _price_provider(provider, requirements, question):
    from copilot.pricing_tools.pricing_calc import PriceUnavailable, load_pricing, usd_to_inr
    from copilot.pricing_tools.pricing_evidence import lookup
    from copilot.pricing_tools.pricing_intent import price_item

    api, region, workload = requirements["api"], requirements["region"], requirements["monthly_workload"]
    if provider == "Ola Maps" and region.casefold().strip() != "india":
        return _pricing_gap("No rate card for the requested region is verified in the pricing snapshot.")
    if provider == "Google Maps Platform" and api == "directions" and re.search(r"\blegacy\b", question, re.I):
        return _pricing_gap("The Legacy Directions price cannot be matched to this workload by the current calculator.")
    if api == "autocomplete" and provider == "Mapbox" and workload["unit"] != "sessions":
        return _pricing_gap("Search Box pricing requires the monthly number of sessions.")
    if (api == "autocomplete" and provider in {"Google Maps Platform", "Ola Maps"}
            and workload["unit"] == "sessions" and not workload.get("keystrokes_per_session")):
        return _pricing_gap("Requests per session are needed to price this session workload.")
    try:
        quotes = price_item(_price_input(provider, api, region, workload, question))
    except PriceUnavailable:
        return _pricing_gap("No list price for this API, region and workload could be verified.")
    except (TypeError, ValueError, KeyError):
        return _pricing_gap("The published billing unit could not be matched to this workload.")

    scenarios = {}
    for quote in quotes:
        scenarios.setdefault(quote.get("group_suffix") or "Requested workload", []).append(quote)
    estimates, gaps = [], []
    config = load_pricing()
    for name, rows in scenarios.items():
        evidence = [lookup(row["sku"]) for row in rows]
        currencies = {row["currency"] for row in rows}
        if not all(evidence) or len(currencies) != 1:
            gaps.append(f"Rate-card evidence is incomplete for {name.strip()}.")
            continue
        currency = rows[0]["currency"]
        sources = {(hit["source_url"], hit["relevant_passage"]): {
            "url": hit["source_url"], "span": hit["relevant_passage"],
        } for hits in evidence for hit in hits}
        quote_required = any(row["contact_sales"] for row in rows)
        total = None if quote_required else sum((Decimal(row["cost"]) for row in rows), Decimal(0))
        total_inr = total if total is None or currency == "INR" else usd_to_inr(total)
        estimates.append({
            "scenario": name.strip(), "currency": currency,
            "monthly_cost": str(total) if total is not None else None,
            "monthly_cost_inr": str(total_inr) if total_inr is not None else None,
            "components": [{
                "sku": row["sku"], "label": row["label"], "quantity": row["units"],
                "billing_unit": config["skus"][row["sku"]]["unit"],
                "free_units": row["free_units"], "billable_units": row["billable_units"],
            } for row in rows],
            "source_references": list(sources.values()),
            "assumptions": list(dict.fromkeys(note for row in rows for note in row["notes"])),
        })
        if quote_required:
            gaps.append(f"A vendor quote is needed above the published tiers for {name.strip()}.")
    reason = " ".join(gaps) or None
    if not estimates:
        return _pricing_gap(reason or "No published rate-card evidence could be verified.")
    return {"status": "partial" if gaps else "verified", "estimates": estimates, "reason": reason}


def compare_prices(providers, requirements, question):
    return {provider: _price_provider(provider, requirements, question) for provider in providers}


@lru_cache(maxsize=1)
def _source_providers():
    from copilot.rag.document_retrieval.hybrid import SOURCE_MANIFEST, _source_url_key
    import yaml

    records = yaml.safe_load(SOURCE_MANIFEST.read_text(encoding="utf-8"))["sources"]
    return {_source_url_key(url): record["provider"] for record in records
            if "provider" in record and record.get("kind") in {"html", "docs", "openapi", "github", "official", "reference", "markdown"}
            for url in (record["url"], *record.get("aliases", []))}


def provider_passages(provider, passages, dimension, requirements, original):
    from copilot.rag.document_retrieval.hybrid import _source_url_key

    sources = _source_providers()
    result = []
    product = _document_product(provider, requirements["api"], original)
    region = re.compile(rf"(?<!\w){re.escape(requirements['region'])}(?!\w)", re.I)
    without_traffic = "without live traffic" in _request_options(original)
    wants_two_wheeler = bool(re.search(r"\b(?:two[- ]wheel\w*|motorcycl\w*)\b", original, re.I))
    for passage in passages:
        url = _source_url_key(passage["source_url"])
        if sources.get(url) != provider:
            continue
        span = passage["relevant_passage"]
        heading = span.split("\n", 1)[0]
        if product.startswith("Routes API ") and ("/documentation/directions/" in url
                                                   or "/documentation/distance-matrix/" in url
                                                   or "(legacy)" in heading.casefold()):
            continue
        if (product == "Routes API Compute Routes" and "Compute Route Matrix" in span
                and not re.search(r"\bCompute Routes\b", span)):
            continue
        if dimension == "coverage":
            if not wants_two_wheeler and re.search(r"\b(?:two[- ]wheel\w*|motorcycl\w*)\b", heading, re.I):
                continue
            if not region.search(span):
                continue
            if without_traffic and "traffic coverage" in heading.casefold():
                continue
        result.append(passage)
    return result


def _request_options(original):
    from copilot.pricing_tools.pricing_intent import regex_hints

    hints = regex_hints(original.lower())
    version = re.findall(r"\b(?:legacy|v\d+(?:\.\d+)*)\b", original, re.I)
    traffic = {True: "with live traffic", False: "without live traffic"}.get(hints.get("traffic"))
    return ", ".join(dict.fromkeys(version + ([traffic] if traffic else [])))


def _document_product(provider, api, original):
    if provider == "Google Maps Platform" and api in {"directions", "distance_matrix"}:
        if not re.search(r"\blegacy\b", original, re.I):
            return "Routes API Compute Routes" if api == "directions" else "Routes API Compute Route Matrix"
    return f"{_API_NAMES[api]} API"


def document_search_query(provider, dimension, requirements, original):
    region = requirements["region"]
    topic = ("usage limits request quota per minute maximum coordinates waypoints batch size" if dimension == "limits"
             else f"geographic coverage in {region} country availability service regions")
    product = _document_product(provider, requirements["api"], original)
    options = _request_options(original)
    if (dimension == "coverage" and provider == "Mapbox" and requirements["api"] == "directions"
            and "without live traffic" in options):
        options = options.replace("without live traffic", "mapbox/driving standard automotive routing")
    return f"{provider}: {product} {topic} {options}".strip()


def document_query(provider, dimension, requirements, original):
    api, region = _API_NAMES[requirements["api"]], requirements["region"]
    workload = requirements["monthly_workload"]
    scope = f"{api} in {region}, {workload['quantity']:,} {workload['unit'].replace('_', ' ')} per month"
    if "origins" in workload:
        scope += f", {workload['origins']} origins and {workload['destinations']} destinations per matrix"
    if "keystrokes_per_session" in workload:
        scope += f", {workload['keystrokes_per_session']} keystrokes per session"
    options = _request_options(original)
    if options:
        scope += f", {options}"
    product = _document_product(provider, requirements["api"], original)
    question = f"{provider}: Report {_DOCUMENT_TOPICS[dimension]} for {scope}. Product: {product}."
    if dimension == "limits":
        question += " A product-wide limit is relevant if it applies to this API. Do not infer peak usage from monthly volume."
    return question


def document_selection_rule(dimension):
    if dimension == "limits":
        return (
            "Choose passages that state at least one concrete request limit, quota, or parameter limit "
            "for the named API. A product-wide limit applies without a country or monthly volume "
            "in the citation. Do not require the passage to cover every kind of limit. "
            "Exclude other products, versions and generic billing descriptions."
        )
    return (
        "Choose only passages that explicitly confirm or rule out the named API's coverage in the "
        "requested area. A country-level table row or an explicit geographic restriction is sufficient. "
        "Exclude general maps coverage, other APIs, and unsubstantiated claims about traffic or capacity."
    )


def coverage_gap(provider, dimension, requirements, original):
    if (dimension == "coverage" and provider == "Mapbox" and requirements["api"] == "directions"
            and "without live traffic" in _request_options(original)):
        return "No retrieved Mapbox documentation verified coverage for the standard driving profile in the requested region."
    return None


def document_result(draft, reason=None):
    if draft is None:
        return {"status": "missing_evidence", "findings": [],
                "reason": reason or "No retrieved passage verified this dimension for the shared requirements."}
    return {"status": "verified", "findings": [
        {"url": citation["url"], "span": citation["span"]} for citation in draft["citations"]
    ], "reason": None}


def assemble(providers, requirements, prices, documents):
    assumptions = [
        "All providers are compared for the same API, operating region, and monthly workload.",
        _RATE_ASSUMPTION,
        "Price scenarios apply only to their stated SKU and billing assumptions. Monthly usage does not establish peak request load.",
    ]
    if requirements["region"].casefold().strip() == "india" and "Google Maps Platform" in providers:
        assumptions.append("Any Google India estimate assumes eligibility for the India price list.")
    if any(estimate["currency"] == "USD" for price in prices.values() for estimate in price["estimates"]):
        from copilot.pricing_tools.pricing_calc import load_pricing

        fx = load_pricing()["fx"]
        assumptions.append(f"USD estimates use the archived rate of {fx['usd_inr']} INR per USD ({fx['as_of']}).")

    workload = requirements["monthly_workload"]
    if workload["unit"] == "sessions" and prices.get("Google Maps Platform", {}).get("estimates"):
        assumptions.append("Google autocomplete uses request-based pricing for this comparison.")
    workload_text = f"{workload['quantity']:,} {workload['unit'].replace('_', ' ')} per month"
    sections = [f"Comparison for {_API_NAMES[requirements['api']]} in {requirements['region']}, {workload_text}."]
    if "origins" in workload:
        sections.append(f"Each matrix has {workload['origins']} origins and {workload['destinations']} destinations.")
    elif "keystrokes_per_session" in workload:
        sections.append(f"Each autocomplete session has {workload['keystrokes_per_session']} keystrokes.")
    citations = {}
    provider_results = []
    incomplete = False

    def reference(source):
        key = source["url"], source["span"]
        if key not in citations:
            citations[key] = len(citations) + 1
        return f"[{citations[key]}]"

    for provider in providers:
        row = {"provider": provider, "pricing": prices[provider], **documents[provider]}
        provider_results.append(row)
        lines = [provider]
        for estimate in row["pricing"]["estimates"]:
            amount = (f"{estimate['currency']} {estimate['monthly_cost']} per month"
                      if estimate["monthly_cost"] is not None else "Vendor quote required")
            if estimate["currency"] == "USD" and estimate["monthly_cost_inr"] is not None:
                amount += f" (about INR {estimate['monthly_cost_inr']} per month)"
            refs = " ".join(map(reference, estimate["source_references"]))
            lines.append(f"- Cost ({estimate['scenario']}): {amount} {refs}")
            lines.extend(f"  Assumption: {note}" for note in estimate["assumptions"])
        for dimension in DOCUMENT_DIMENSIONS:
            evidence = row[dimension]["findings"]
            summary = row[dimension].get("summary")
            if summary:
                refs = " ".join(map(reference, evidence))
                lines.append(f"- {dimension.title()}: {summary} {refs}")
            else:
                for finding in evidence:
                    lines.append(f"- {dimension.title()}: {finding['span']} {reference(finding)}")
        for dimension in DIMENSIONS:
            if row[dimension]["reason"]:
                incomplete = True
                lines.append(f"- {dimension.title()}: {row[dimension]['reason']}")
        sections.append("\n".join(lines))
    sections.append("\n".join(f"- {assumption}" for assumption in assumptions))
    draft = make_draft("\n\n".join(sections), [
        {"url": url, "span": span, "supports_claim": span, "quote_or_summary": "verbatim"}
        for url, span in citations
    ])
    comparison = {
        "applicable": True, "providers": providers, "dimensions": list(DIMENSIONS),
        "equivalent_requirements": requirements, "provider_results": provider_results,
        "assumptions": assumptions, "source_urls": list(dict.fromkeys(url for url, _ in citations)),
        "notes": "Some results could not be verified for the shared requirements." if incomplete else None,
    }
    return draft, comparison
