"""Extract explicit customer facts with evidence for staff follow-up selection."""
import re

from copilot.safety.provider_evidence import (ambiguous_current_providers, current_provider_hit,
                                            provider_mentions, provider_retractions)
from copilot.safety.pii import redact
from copilot.pricing_tools.qualification import explicit_geographies
from copilot.qualification.workload import asserted_workload_evidence
from copilot.qualification.extraction import clauses, _customer_clause


def _evidence_clause(text, match):
    for offset, clause, ending in clauses(text):
        if offset <= match.start() < offset + len(clause):
            if not _customer_clause(clause, ending) or re.match(r'\s*(?:did|have|has|how|when|where|why)\b', clause, re.I):
                return None
            return offset, clause
    return None


def _spike_observation(text, match):
    context = _evidence_clause(text, match)
    if not context:
        return None
    offset, clause = context
    prefix = clause[:match.start() - offset]
    suffix = clause[match.end() - offset:]
    if re.search(r"\b(?:should|would|expect(?:ed)?|potential|not checked|haven['’]t checked|do not know|don't know)\b", clause, re.I):
        return None
    label = re.match(r'\s*[:=]\s*(yes|no|true|false)\b', suffix, re.I)
    if label:
        value = label[1].casefold() in {'yes', 'true'}
    elif re.search(r'\b(?:no|without)\s+(?:any\s+)?$', prefix, re.I) or re.search(
        r"\b(?:have not|haven['’]t|did not|didn['’]t|do not|don['’]t|not)\s+(?:notice[ds]?|observed?|see[n]?|detect(?:ed)?|record(?:ed)?|experienced?)\s+(?:any\s+)?$", prefix, re.I
    ) or re.match(r'\s*(?:were|are|have been)\s+not\s+(?:observed|noticed|detected|recorded)\b', suffix, re.I):
        value = False
    elif re.search(r'\b(?:noticed|observed|saw|seen|detected|recorded|experienced|had|have|there (?:are|were))\s+(?:some\s+)?$', prefix, re.I) or re.match(
        r'\s*(?:(?:are|were|have been)\s+)?(?:present|observed|noticed|detected|recorded|reported)\b', suffix, re.I
    ):
        value = True
    else:
        return None
    start = offset + len(clause) - len(clause.lstrip())
    end = offset + len(clause.rstrip())
    return value, start, end


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

        mentions = provider_mentions(text)
        if mentions:
            start, end = min(item['start'] for item in mentions), max(item['end'] for item in mentions)
            facts['mentioned_providers'] = {
                'field': 'mentioned_providers', 'value': [item['value'] for item in mentions],
                'source': source, 'evidence': text[start:end], 'start': start, 'end': end,
            }
            facts.pop('provider', None)
            if len(mentions) == 1:
                facts['provider'] = {'field': 'provider', 'source': source, **mentions[0]}
        current = current_provider_hit(text)
        if ambiguous_current_providers(text) or facts.get('current_provider', {}).get('value') in provider_retractions(text):
            facts.pop('current_provider', None)
        if current:
            facts['current_provider'] = {
                'field': 'current_provider', 'source': source,
                **{key: current[key] for key in ('value', 'evidence', 'start', 'end')},
            }
        for match in re.finditer(r"(?<![\d.])-?\d{1,3}\.\d+\s*,\s*-?\d{1,3}\.\d+(?:;\s*-?\d{1,3}\.\d+\s*,\s*-?\d{1,3}\.\d+)*", text):
            # Preserve submitted order. Coordinate validity is a separate check.
            add("coordinates", match.group().replace(" ", ""), match)
        for match in re.finditer(r"\b(?:HTTP\s+|returns?\s+|fail\w*\s+with\s+)([45]\d\d(?:/[45]\d\d)*)\b", text, re.I):
            add("http_status", match.group(1).split("/"), match)
        for match in re.finditer(r"\b(NoSegment|ZERO_RESULTS|OVER_QUERY_LIMIT|NOT_FOUND|REQUEST_DENIED)\b", text, re.I):
            code = "NoSegment" if match.group(1).casefold() == "nosegment" else match.group(1).upper()
            add("error_code", code, match)
        for match in re.finditer(r"\b([\d,]+)\s+(?:[\w-]+\s+){0,4}(?:routes|requests|calls|lookups)\s+(?:a|per|/)\s*(month|year|day|minute|second)\b", text, re.I):
            if not asserted_workload_evidence(text, match.group(), start=match.start()):
                continue
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
        for field, pattern in (
            ('account_reference', r'\baccount\s+(?:ID|reference|identifier)\s*[:=]\s*(?P<value>[\w.-]+)'),
            ('prediction_query', r'\b(?:prediction\s+query|query\s+sent|search\s+query)\s*[:=]\s*(?P<value>[^;\n]+)'),
            ('returned_prediction', r'\b(?:returned\s+prediction|prediction\s+returned|prediction)\s*[:=]\s*(?P<value>[^;\n]+)'),
            ('exposure_time', r'\b(?:exposure\s+time|key\s+(?:was\s+)?(?:exposed|leaked))\s*(?:[:=]|at|on)?\s*(?P<value>(?:today|yesterday|\d)[^.;\n]*)'),
        ):
            for match in re.finditer(pattern, text, re.I):
                if not _evidence_clause(text, match):
                    continue
                add(field, match['value'].strip(), match)
        for match in re.finditer(r"\b(?:unusual|unexpected)\s+(?:usage|traffic)\s+spikes?\b", text, re.I):
            observation = _spike_observation(text, match)
            if observation:
                value, start, end = observation
                facts['unusual_usage_spikes'] = {'field': 'unusual_usage_spikes', 'value': value,
                    'source': source, 'evidence': text[start:end], 'start': start, 'end': end}
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
