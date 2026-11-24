"""Extract explicit customer facts with evidence for staff follow-up selection."""
import re

from copilot.rag.document_retrieval.query_analyzer import PROVIDER_KEYWORDS
from copilot.safety.pii import redact
from copilot.pricing_tools.qualification import explicit_geographies


def extract_supplied_facts(enquiry):
    """Keep latest explicit values and their source. Assistant claims are excluded."""
    facts = {}
    sources = [
        (f"history[{index}]", turn["text"])
        for index, turn in enumerate(enquiry.get("history", [])) if turn["role"] == "user"
    ]
    sources.append(("query", enquiry["query"]))
    for source, raw in sources:
        text = redact(raw)

        def add(field, value, match):
            facts[field] = {"field": field, "value": value, "source": source,
                            "evidence": match.group(), "start": match.start(), "end": match.end()}

        for fact in explicit_geographies(text):
            facts[fact["field"]] = {**fact, "source": source}

        for provider, patterns in PROVIDER_KEYWORDS.items():
            match = next((m for pattern in patterns if (m := re.search(pattern, text, re.I))), None)
            if match:
                add("provider", provider, match)
        for match in re.finditer(r"(?<![\d.])-?\d{1,3}\.\d+\s*,\s*-?\d{1,3}\.\d+(?:;\s*-?\d{1,3}\.\d+\s*,\s*-?\d{1,3}\.\d+)*", text):
            # Preserve submitted order. Coordinate validity is a separate check.
            add("coordinates", match.group().replace(" ", ""), match)
        for match in re.finditer(r"\b(?:HTTP\s+|returns?\s+|fail\w*\s+with\s+)([45]\d\d(?:/[45]\d\d)*)\b", text, re.I):
            add("http_status", match.group(1).split("/"), match)
        for match in re.finditer(r"\b(NoSegment|ZERO_RESULTS|OVER_QUERY_LIMIT|NOT_FOUND|REQUEST_DENIED)\b", text, re.I):
            code = "NoSegment" if match.group(1).casefold() == "nosegment" else match.group(1).upper()
            add("error_code", code, match)
        for match in re.finditer(r"\b([\d,]+)\s+(?:[\w-]+\s+){0,4}(?:routes|requests|calls|lookups)\s+(?:a|per|/)\s*(month|year|day|minute|second)\b", text, re.I):
            add("workload", int(match.group(1).replace(",", "")), match)
            add("workload_period", match.group(2).lower(), match)
        for match in re.finditer(r"\b(?:don['’]t|do not|never)\s+(?:send|set|include|supply)\s+(?:any\s+|a\s+)?User-Agent\b", text, re.I):
            add("user_agent_present", False, match)
        for match in re.finditer(r"\blimit\s*=\s*(\d+)\b", text, re.I):
            add("limit_parameter", int(match.group(1)), match)
        for match in re.finditer(r"\b(\d+)\s*(?:stations\s*)?[×x]\s*(\d+)(?:\s+offices)?\b", text, re.I):
            add("origin_count", int(match.group(1)), match)
            add("destination_count", int(match.group(2)), match)
            add("matrix_elements", int(match.group(1)) * int(match.group(2)), match)
        for match in re.finditer(r"\bmore than\s+(\d+)\s+waypoints\b", text, re.I):
            add("waypoint_lower_bound_exclusive", int(match.group(1)), match)
        for match in re.finditer(r"\bdeparture_time\s*=\s*([\w:+-]+)", text):
            add("departure_time", match.group(1), match)
        for match in re.finditer(r"\bTKT-\d+\b", text):
            add("ticket_id", match.group(), match)
        for match in re.finditer(r"\bafter we rotated OAuth credentials\b", text, re.I):
            add("failure_after_credential_rotation", True, match)
        for match in re.finditer(r"\b(?:let['’]s leave that open|please proceed with what we know|answer based on my earlier message)\b", text, re.I):
            add("proceed_without_more_questions", True, match)
        for match in re.finditer(r"\b(request(?: body| path| URL)?|error message|response body|result filters|API response)\s*[:=]\s*([^\n]+)", text, re.I):
            field = {
                "request": "request_example", "request path": "request_example",
                "request url": "request_example", "request body": "request_body",
                "error message": "error_message", "response body": "error_message",
                "result filters": "result_filters", "api response": "observed_api_result",
            }[match.group(1).lower()]
            value = re.sub(r"(?i)(bearer\s+|(?:api[_-]?key|access_token|token|password|client_secret)[=:]\s*)[^\s&\"']+",
                           r"\1[REDACTED]", match.group(2))
            safe_match = match
            add(field, value, safe_match)
            facts[field]["evidence"] = re.sub(
                r"(?i)(bearer\s+|(?:api[_-]?key|access_token|token|password|client_secret)[=:]\s*)[^\s&\"']+",
                r"\1[REDACTED]", match.group(),
            )
            if field == "request_body":
                facts["request_example"] = {**facts[field], "field": "request_example"}
    return list(facts.values())


_ALIASES = {
    "duration_of_usage": "workload_period", "usage_duration": "workload_period",
    "billing_period": "workload_period", "monthly_volume": "workload",
    "missing_user_agent": "user_agent_present", "user_agent_missing": "user_agent_present",
    "user_agent_presence": "user_agent_present",
    "location_coordinates": "coordinates", "missing_location_coordinates": "coordinates",
}


def repeated_fact_fields(candidate, supplied):
    """Suppress only wholly known candidates. Unknown or additional facts keep them."""
    fields = candidate.get("facts", [])
    if not isinstance(fields, list) or not fields:
        return []
    if fields == ["missing_fact"]:
        fields = [candidate.get("field", "")]
    canonical = {_ALIASES.get(field, field) for field in fields}
    known = {fact["field"] for fact in supplied}
    return sorted(canonical) if canonical and canonical <= known else []
