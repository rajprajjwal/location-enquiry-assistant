"""Select and group missing facts that support one staff decision."""

from dataclasses import dataclass
import re

from copilot.rag.document_retrieval.query_analyzer import detect


@dataclass(frozen=True)
class Fact:
    field: str
    phrase: str
    supplied: str = ""
    asked: str = ""


@dataclass(frozen=True)
class Plan:
    field: str
    facts: tuple[Fact, ...]
    template: str


_COORDINATES = Fact("coordinates", "the submitted coordinates",
                    r"\b-?\d{1,3}\.\d+\s*[,/]\s*-?\d{1,3}\.\d+\b", r"\b(?:coordinates|latitude and longitude)\b")
_ROUTE = Fact("route_endpoints", "the origin and destination",
              r"\borigin\s*[=:].{1,110}\bdestination\s*[=:]", r"\borigin\b.{0,55}\bdestination\b")
_PROFILE = Fact("routing_profile", "the routing profile used",
                r"\b(?:profile\s*[:=]|using (?:the )?(?:driving|walking|cycling) profile)\b", r"\brouting profile\b")
_DEPARTURE = Fact("departure_time", "the departure time",
                  r"\bdeparture_time\s*[:=]\s*\S+|\bdepart(?:ed|s|ure)? (?:at|time) \d", r"\bdeparture time\b")
_EXPECTED = Fact("expected_location", "the expected result", r"\bexpected (?:address|street)\s*[:=]", r"\bexpected (?:address|street|result)\b")
_RETURNED = Fact("returned_location", "the returned result", r"\breturned (?:address|street)\s*[:=]", r"\breturned (?:address|street|result)\b")
_PEAK = Fact("peak_rate", "the peak requests per minute at the time",
             r"\b[\d,.]+\s+(?:batch\s+)?(?:requests?|calls?|lookups?)\s*(?:per|/)\s*(?:second|minute|min|sec)\b",
             r"\b(?:peak|requests per minute|request rate)\b")
_BATCH = Fact("batch_size", "the number of coordinates in a typical batch",
              r"\b[\d,.]+\s+(?:coordinates|points)\s+per batch|\bbatch size\s*[:=]\s*\d", r"\b(?:batch size|coordinates per batch)\b")
_PROVIDER = Fact("provider", "the provider handling autocomplete requests", asked=r"\bwhich (?:map )?provider\b")
_TOKEN = Fact("same_session_token", "whether the Place Details call uses the same session token",
              r"\b(?:uses?|using|with|send)\s+(?:the\s+)?(?:same|different) session token\b", r"\bsame session token\b")
_VERSION = Fact("api_version", "the Places API version",
                r"\bplaces (?:api|autocomplete)\s*\((?:new|legacy)\)", r"\b(?:places api version|new or legacy)\b")
_CLIENT = Fact("integration_provider", "whether the client calls Google directly or through another provider",
               r"\b(?:call(?:ing)?|use|using) google places directly\b", r"\b(?:calling google places directly|through another provider)\b")
_SCOPE = Fact("units_scope", "whether you mean the API response units or how to display them",
              asked=r"\b(?:response units|display units)\b")
_SEARCH = Fact("search_term", "one redacted search term that returned no results",
               r"\b(?:search term|query|input)\s*[:=]\s*['\"]?\w+", r"\b(?:redacted search term|exact input)\b")
_AREA = Fact("search_area", "the city or search area used",
             r"\b(?:search area|city|region)\s*[:=]", r"\b(?:city or search area|search region)\b")
_LENGTH = Fact("input_length", "the character count of a rejected address",
               r"\b[\d,.]+\s*characters\b", r"\b(?:how many characters|character count)\b")
_ERROR = Fact("error_details", "the exact error code or message",
              r"\b(?:HTTP\s+[45]\d\d|(?:returns?|gets?|code)\s+['\"]?(?:[45]\d\d|[A-Z][A-Z_]{4,}))\b",
              r"\b(?:exact error|error code|error message)\b")
_LANGUAGES = Fact("input_languages", "the languages users need to type in", asked=r"\bwhich languages\b")
_SCRIPT = Fact("input_script", "whether users type in native script or Latin-letter transliteration",
               r"\b(?:type|enter)\s+(?:in\s+)?(?:the )?(?:native script|latin|transliterated)\b", r"\b(?:transliterat|native script)")
_SHORTLIST = Fact("provider_shortlist", "the providers you are considering, if any", asked=r"\bproviders are you considering\b")
_WAYPOINTS = Fact("waypoint_sequence", "the waypoints in the order sent",
                  r"\bwaypoints\s*[:=]\s*\S", r"\bwaypoints\b.{0,50}\border\b")
_ROUTE_COMPARISON = Fact("same_route", "whether origin, destination, and waypoints match", asked=r"\bsame (?:route|origin|waypoints)")
_TIME_COMPARISON = Fact("same_departure", "whether departure times match", asked=r"\bsame departure time\b")
_POSTCODES = Fact("failing_postcodes", "a representative failing pair of postcodes", asked=r"\b(?:pair of|origin and destination) .{0,15}postcodes")
_TRANSIT_TIME = Fact("transit_time", "the departure or arrival time",
                     r"\b(?:departure_time|arrival_time)\s*[:=]\s*\S+", r"\b(?:arrival time|departure time)\b")

_QUOTA = re.compile(
    r"\b(?:returns?|receiv(?:e|ed)|got|getting|hit|saw|respond(?:ed|s)?\s+with|fails?\s+with)"
    r"\s+['\"]?(?:an?\s+)?(?:http\s+)?(?:429|over_query_limit)\b"
    r"|\b(?:429|over_query_limit)\s+(?:errors?\s+)?(?:during|since|while|after|from)\b", re.I,
)
_FAILED = re.compile(r"\b(?:returns? nothing|zero_results|null|reject\w*|doesn.t return|"
                     r"wrong|impossibly|unexpectedly short|sometimes returns?)\b", re.I)
PROCEED = re.compile(r"\b(?:go ahead|please proceed|leave that open|answer (?:with|based on))\b", re.I)
OPEN_QUALIFICATION = re.compile(r"\b(?:what|which)\b[^?.!]{0,100}\b(?:ask|confirm|clarify|record|include)\b", re.I)


def plan_follow_up(query, api):
    """Prefer the observed symptom to broad API keywords."""
    text = query.casefold()
    if _QUOTA.search(text):
        if "batch" in text:
            return Plan("batch_limit", (_PEAK, _BATCH),
                        "Around the time of the rate-limit error, how many batch requests per minute were you sending, "
                        "and how many coordinates were in a typical batch?")
        if ("over_query_limit" in text or "project" in text) and api in {"directions", "distance_matrix"}:
            return Plan("peak_rate", (_PEAK,),
                        "When the error occurred, roughly how many requests per minute were being sent across the "
                        "entire Google Cloud project, including traffic from other apps or services?")
        return Plan("peak_rate", (_PEAK,), "What was the peak request rate per minute when the rate-limit error occurred?")

    if api == "autocomplete":
        if "place details pro" in text and re.search(r"\b(?:session|pay|bill\w*)\b", text):
            return Plan("session_billing", (_PROVIDER, _TOKEN),
                        "Which provider handles your autocomplete requests, and does the Place Details Pro call use "
                        "the same session token as the autocomplete requests?")
        if "java" in text and "session token" in text:
            return Plan("session_client", (_CLIENT, _VERSION),
                        "Are you calling Google Places directly or through another provider’s Java client, "
                        "and are you using Places API (New) or Legacy?")
        if re.search(r"\b(?:language\w*|hindi|transliter\w*)\b", text) and re.search(r"\b(?:which|compare)\b", text):
            return Plan("language_input", (_LANGUAGES, _SCRIPT, _SHORTLIST),
                        "Which languages do your users need to type in, will they use the native script or Latin-letter "
                        "transliteration, and which providers are you considering, if any?")
        if _FAILED.search(text) and re.search(r"\b(?:long|pasted|length|characters)\b", text):
            return Plan("input_length_error", (_LENGTH, _ERROR),
                        "How many characters were in one address that was rejected, and what exact error code or message came back?")
        if _FAILED.search(text) and re.search(r"\b(?:queries|query|suggestions|types)\b", text):
            return Plan("autocomplete_reproduction", (_SEARCH, _AREA),
                        "Can you share one redacted search term that returned no results and the city or search area you used?")

    if api == "directions":
        if "traffic_model" in text and re.search(r"\b(?:optimistic|best_guess|pessimistic)\b", text):
            return Plan("comparable_routes", (_TIME_COMPARISON, _ROUTE_COMPARISON),
                        "Were the two requests sent with the same departure time, origin, destination, and waypoints?")
        if "zero_results" in text and re.search(r"\bwaypoint\w*\b", text):
            return Plan("waypoint_sequence", (_WAYPOINTS,),
                        "Can you share the waypoints in the order you sent them, using a redacted example of the failing API request?")
        if "zero_results" in text and "transit" in text:
            return Plan("route_endpoints", (_ROUTE,),
                        "Can you share the origin and destination from one transit request that returned ZERO_RESULTS?")

    if api == "distance_matrix":
        if re.search(r"\bunits?\b", text) and "distance" in text and "duration" in text:
            if re.search(r"\b(?:raw response|response fields|display in|format in|convert to)\b", text):
                return None
            return Plan("units_scope", (_SCOPE,),
                        "Are you asking what units the API returns for distance and duration, or how to display those values "
                        "in your app, such as kilometres and minutes?")
        if "null" in text:
            return Plan("null_matrix_cell", (_ROUTE, _PROFILE),
                        "Can you share one origin–destination pair that returned null and the routing profile used for that request?")
        if "zero_results" in text and re.search(r"\bpostcode\w*\b", text):
            return Plan("transit_matrix_example", (_POSTCODES, _TRANSIT_TIME),
                        "Can you share one pair of postcodes that returned ZERO_RESULTS, along with the departure or arrival time you used?")
        if "duration_in_traffic" in text and re.search(r"\b(?:short|low|unexpected)\w*\b", text):
            return Plan("traffic_duration_example", (_ROUTE, _DEPARTURE),
                        "Can you share the origin, destination, and departure time from one request that returned an unexpectedly short duration?")

    if api == "reverse_geocode" and _FAILED.search(text):
        if "zero_results" in text and "phone" in text and "browser" in text:
            return Plan("coordinates", (_COORDINATES,),
                        "Can you share the exact latitude and longitude from one phone lookup that returned ZERO_RESULTS so we can reproduce it?")
        if re.search(r"\b(?:address|street|location)\w*\b", text):
            noun = "street" if re.search(r"\bstreet\b", text) else "address"
            return Plan("reverse_geocode_example", (_COORDINATES, _RETURNED, _EXPECTED),
                        f"Can you share one example with the coordinates you submitted, the {noun} returned, "
                        f"and the {noun} you expected, with private details removed?")

    return None


def staff_question(enquiry, api, active):
    """Use facts that are still missing. Keep the original pending question separate."""
    query = enquiry["query"]
    if PROCEED.search(query) and enquiry.get("history"):
        return []
    plan = plan_follow_up(query, api)
    if plan is None:
        return None
    user_turns = [query, *(turn["text"] for turn in enquiry.get("history", []) if turn["role"] == "user")]
    prior_questions = [
        turn["text"] for turn in enquiry.get("history", []) if turn["role"] == "assistant"
    ] + [question["text"] for question in active]
    known = {item["field"] for item in enquiry.get("known_facts", [])
             if item.get("field") and item.get("value") is not None}
    if any(detect(text)["providers"] for text in user_turns):
        known.add("provider")
    missing = [fact for fact in plan.facts if fact.field not in known
               and not (fact.supplied and any(re.search(fact.supplied, text) for text in user_turns))
               and not (fact.asked and any(re.search(fact.asked, text, re.I) for text in prior_questions))]
    if not missing:
        return []
    if len(missing) == len(plan.facts):
        return [{"field": plan.field, "text": plan.template}]
    phrases = [fact.phrase for fact in missing]
    details = phrases[0] if len(phrases) == 1 else ", ".join(phrases[:-1]) + " and " + phrases[-1]
    return [{"field": plan.field, "text": f"Can you share {details}?"}]
