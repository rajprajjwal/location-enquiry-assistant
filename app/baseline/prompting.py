"""
Prompt Engineering Baseline
============================
mework Three prompting strategies on Qwen/Qwen3-8B (≤8B, no tools, no agent loop, no RAG).

Strategies
----------
1. few_shot_structured   — zero-shot system schema + 3 labelled examples, temp=0
2. chain_of_thought      — 5-step CoT + self-consistency (3 samples, majority vote), temp=0.6
3. decomposition         — 5 sub-problem calls + 1 synthesis call, temp=0

Scorer (same dimensions as the agent evaluator)
------------------------------------------------
- accuracy       : intent correct vs gold  (0 or 1)
- grounding      : answer cites a KB-style source OR references a known fact  (0–1)
- completeness   : fraction of gold missing_info fields captured  (0–1)
- latency_s      : wall-clock seconds for the strategy
- cost_usd       : estimated cost at $0.0005 / 1K tokens (proxy for vLLM token count)
- parse_ok       : JSON parsed without error  (0 or 1)
- failure        : first failure mode name, or None

Pass criteria (per frozen-set run)
-----------------------------------
- All 3 strategies fully run with all 6 metrics logged for every record
- Best strategy named in results table with score delta vs the other two
"""
import json
import re
import time
from typing import Optional
from dataclasses import dataclass, field, asdict

from app.llm import get_llm
from langchain.schema import SystemMessage, HumanMessage

# ── Token cost proxy ───────────────────────────────────────────────────────────
_COST_PER_1K = 0.0005   # $0.0005 per 1K tokens (vLLM proxy rate)

def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

def _cost(prompt: str, response: str) -> float:
    tokens = _estimate_tokens(prompt) + _estimate_tokens(response)
    return round(tokens * _COST_PER_1K / 1000, 6)


# ── Documented failure modes ───────────────────────────────────────────────────
FAILURE_MODES = {
    "json_fence_wrapping":
        "Model wraps JSON in ```json``` fences — breaks json.loads() directly.",
    "truncated_json":
        "Model stops mid-JSON near 8192 token limit.",
    "cot_think_tag_bleed":
        "Qwen3 <think>...</think> reasoning leaks into final answer.",
    "self_consistency_drift":
        "3 CoT samples produce 3 different intents — no majority possible.",
    "decomposition_contradiction":
        "Sub-problem answers contradict each other; synthesis picks wrong one.",
    "few_shot_field_copy":
        "Model copies field values from examples instead of from the query.",
    "over_escalation":
        "Model escalates every support query to L3 regardless of severity.",
    "empty_missing_fields":
        "Model returns missing_info=[] when context clearly lacks required fields.",
    "confidence_anchoring":
        "Model always returns confidence=0.9 regardless of actual uncertainty.",
    "hallucinated_pricing":
        "Model invents pricing figures not present in the prompt.",
}


# ── GT record for baseline (no RAG — gold_chunks not used here) ───────────────
@dataclass
class BaselineGTRecord:
    id:                  str
    query:               str
    gold_intent:         str
    gold_missing_fields: list[str]   # expected missing_info items
    gold_keywords:       list[str]   # keywords that must appear for grounding check
    workflow:            str = "sales"
    difficulty:          str = "medium"


# ── Frozen GT set (26 records across all 4 APIs, sales + support, 3 difficulties)
FROZEN_GT: list[BaselineGTRecord] = [
    # ── Directions — Sales ──────────────────────────────────────────────────
    BaselineGTRecord("dir-s-01",
        "We need to track 500 delivery vehicles in real time across Europe with sub-metre accuracy.",
        "fleet_tracking_qualification",
        ["accuracy_requirement","platform","budget","timeline","decision_maker","compliance"],
        ["accuracy","fleet","Europe","tracking"], "sales", "easy"),
    BaselineGTRecord("dir-s-02",
        "Compare Directions API providers on pricing for 100K requests per month with real-time traffic.",
        "pricing_comparison",
        ["region","billing_unit","traffic_countries"],
        ["pricing","100K","traffic","Directions"], "sales", "medium"),
    BaselineGTRecord("dir-s-03",
        "Does your Directions API support truck routing with height and weight restrictions?",
        "capability_query",
        ["plan_level","vehicle_dimensions","region"],
        ["truck","height","weight","Professional","Enterprise"], "sales", "easy"),
    BaselineGTRecord("dir-s-04",
        "Which provider supports the most waypoints per Directions API request?",
        "capability_comparison",
        ["plan_level","use_case"],
        ["waypoints","23","150","Enterprise"], "sales", "medium"),
    BaselineGTRecord("dir-s-05",
        "What are the overage charges for Directions API if we exceed the Standard plan limit?",
        "pricing_query",
        ["current_volume","expected_overage_volume"],
        ["overage","$0.005","500K","Standard"], "sales", "easy"),

    # ── Directions — Support ────────────────────────────────────────────────
    BaselineGTRecord("dir-sup-01",
        "Getting 422 error on every Directions API call. Already checked the URL.",
        "error_diagnosis",
        ["request_payload","missing_parameter_name","error_response_body"],
        ["422","MISSING_PARAMETER","required_fields","origin","destination","mode"], "support", "easy"),
    BaselineGTRecord("dir-sup-02",
        "Directions API traffic duration not returned in response even though I set departure_time.",
        "error_diagnosis",
        ["departure_time_format","mode_parameter","country"],
        ["departure_time","ISO8601","duration_in_traffic_s","driving"], "support", "medium"),

    # ── Distance Matrix — Sales ─────────────────────────────────────────────
    BaselineGTRecord("dm-s-01",
        "Compare Distance Matrix API limits across providers for 500 origins x 500 destinations per request.",
        "limits_comparison",
        ["plan_level","async_batch_needed","monthly_volume"],
        ["25x25","50x50","100x100","async","batch","1000x1000"], "sales", "hard"),
    BaselineGTRecord("dm-s-02",
        "How many Distance Matrix requests do I need for 200 origins x 200 destinations on Professional plan?",
        "calculation_query",
        ["plan_limit","batch_strategy"],
        ["50x50","16","ceil","Professional"], "sales", "hard"),
    BaselineGTRecord("dm-s-03",
        "What is the pricing for Distance Matrix API on Professional plan including overage?",
        "pricing_query",
        ["monthly_volume","expected_overage"],
        ["$999","5M elements","$0.002","overage"], "sales", "easy"),
    BaselineGTRecord("dm-s-04",
        "Does Distance Matrix API support async batch processing for large matrices?",
        "capability_query",
        ["plan_level","matrix_size"],
        ["async","batch","job_id","1000x1000","Enterprise"], "sales", "medium"),

    # ── Distance Matrix — Support ───────────────────────────────────────────
    BaselineGTRecord("dm-sup-01",
        "Distance Matrix API returning 400 MATRIX_TOO_LARGE for our 600x600 request.",
        "error_diagnosis",
        ["current_plan","matrix_size","async_batch_awareness"],
        ["MATRIX_TOO_LARGE","25x25","50x50","100x100","async batch"], "support", "medium"),
    BaselineGTRecord("dm-sup-02",
        "Some Distance Matrix elements return NOT_FOUND. Coordinates look correct.",
        "error_diagnosis",
        ["coordinate_order","routable_area","coordinate_sample"],
        ["NOT_FOUND","lat","lon","coordinate order","routable"], "support", "medium"),

    # ── Autocomplete — Sales ────────────────────────────────────────────────
    BaselineGTRecord("ac-s-01",
        "Compare Autocomplete API coverage across providers for a global address search product.",
        "coverage_comparison",
        ["required_countries","poi_needed","language_requirements"],
        ["195 countries","85","Provider B","180","Provider C","150"], "sales", "medium"),
    BaselineGTRecord("ac-s-02",
        "How do session tokens reduce Autocomplete API billing?",
        "capability_query",
        ["current_billing_model","session_token_awareness"],
        ["session_token","billable session","keystrokes","place detail"], "sales", "medium"),
    BaselineGTRecord("ac-s-03",
        "What is the minimum query length for Autocomplete API and what happens with shorter input?",
        "capability_query",
        [],
        ["2 characters","minimum","q parameter","empty"], "sales", "easy"),

    # ── Autocomplete — Support ──────────────────────────────────────────────
    BaselineGTRecord("ac-sup-01",
        "Autocomplete returns no results for rural addresses in Germany. Works fine for cities.",
        "error_diagnosis",
        ["country_filter_set","query_specificity","coverage_region"],
        ["rural","country filter","coverage","specificity"], "support", "medium"),
    BaselineGTRecord("ac-sup-02",
        "Autocomplete suggestions are not biased to the user's current location.",
        "error_diagnosis",
        ["lat_lon_passed","radius_m_set","device_gps_available"],
        ["lat","lon","radius_m","location bias","GPS"], "support", "easy"),

    # ── Reverse Geocode — Sales ─────────────────────────────────────────────
    BaselineGTRecord("rg-s-01",
        "Compare Reverse Geocode API batch limits across providers for a fleet of 10000 vehicles.",
        "limits_comparison",
        ["plan_level","batch_frequency","monthly_volume"],
        ["1000","batch","Professional","Provider B","Provider C","500"], "sales", "medium"),
    BaselineGTRecord("rg-s-02",
        "What coordinate precision is needed for street-level reverse geocoding results?",
        "capability_query",
        [],
        ["4 decimal places","6 decimal places","street-level","precision"], "sales", "easy"),

    # ── Reverse Geocode — Support ───────────────────────────────────────────
    BaselineGTRecord("rg-sup-01",
        "Reverse Geocode returning APPROXIMATE results instead of a street address for our vehicle positions.",
        "error_diagnosis",
        ["coordinate_precision","coverage_area","location_type_awareness"],
        ["APPROXIMATE","rural","street-level","geometric centre"], "support", "medium"),
    BaselineGTRecord("rg-sup-02",
        "Reverse Geocode returning wrong country for coordinates near a border.",
        "error_diagnosis",
        ["coordinate_order_verified","coordinate_sample"],
        ["coordinate order","lat before lon","lon before lat"], "support", "easy"),

    # ── Escalation / Cross-API ──────────────────────────────────────────────
    BaselineGTRecord("esc-01",
        "Error rate above 10% on location API for 3 hours affecting 200 vehicles. Need urgent help.",
        "escalation_required",
        ["case_id","error_codes","steps_taken","impact_assessment"],
        ["L2 escalation","5%","15 minutes","case_id","impact_assessment"], "support", "hard"),
    BaselineGTRecord("esc-02",
        "Customer needs sub-metre accuracy and 15000 concurrent devices for a national logistics network.",
        "escalation_required",
        ["compliance","budget","timeline","decision_maker"],
        ["Solutions Engineer","UWB","10000 devices","sub-metre"], "sales", "hard"),
    BaselineGTRecord("qual-01",
        "We want to build a food delivery app. What do you need to know from us?",
        "sales_qualification",
        ["use_case","device_count","accuracy_requirement","platform","budget","timeline","decision_maker","compliance"],
        ["BANT","use case","device","accuracy","platform","budget","timeline"], "sales", "easy"),
]


# ── JSON cleaner ───────────────────────────────────────────────────────────────
def _extract_json(raw: str) -> tuple[dict, Optional[str]]:
    text = raw.strip()
    if "```" in text:
        text = "\n".join(l for l in text.split("\n") if not l.strip().startswith("```")).strip()
    # Strip Qwen3 <think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    start = text.rfind("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        return {"raw": raw[:300], "parse_error": True}, "no_json_block_found"
    try:
        return json.loads(text[start:end]), None
    except json.JSONDecodeError as e:
        return {"raw": text[start:start+300], "parse_error": True}, f"json_decode_error: {e}"


# ── Scorer ─────────────────────────────────────────────────────────────────────
@dataclass
class StrategyScore:
    strategy:        str
    record_id:       str
    accuracy:        float = 0.0   # 1.0 if intent matches gold, 0.0 otherwise
    grounding:       float = 0.0   # fraction of gold_keywords found in answer text
    completeness:    float = 0.0   # fraction of gold_missing_fields captured
    latency_s:       float = 0.0
    cost_usd:        float = 0.0
    parse_ok:        float = 0.0   # 1.0 if JSON parsed cleanly
    failure:         Optional[str] = None
    composite:       float = 0.0   # mean(accuracy, grounding, completeness, parse_ok)


def _score_result(
    result:    dict,
    record:    BaselineGTRecord,
    latency_s: float,
    cost_usd:  float,
    failure:   Optional[str],
    strategy:  str,
) -> StrategyScore:
    parse_ok = 0.0 if result.get("parse_error") else 1.0

    # Accuracy — intent match (normalised, partial credit for substring)
    predicted_intent = str(result.get("intent", "")).lower().replace(" ", "_")
    gold_intent      = record.gold_intent.lower()
    if predicted_intent == gold_intent:
        accuracy = 1.0
    elif gold_intent in predicted_intent or predicted_intent in gold_intent:
        accuracy = 0.5
    else:
        accuracy = 0.0

    # Grounding — gold keywords found in full answer text
    answer_text = json.dumps(result).lower()
    if record.gold_keywords:
        hits = sum(1 for kw in record.gold_keywords if kw.lower() in answer_text)
        grounding = round(hits / len(record.gold_keywords), 3)
    else:
        grounding = 1.0 if parse_ok else 0.0

    # Completeness — gold missing_info fields captured
    predicted_missing = [str(m).lower() for m in result.get("missing_info", [])]
    if record.gold_missing_fields:
        hits = sum(
            1 for gf in record.gold_missing_fields
            if any(gf.lower() in pm or pm in gf.lower() for pm in predicted_missing)
        )
        completeness = round(hits / len(record.gold_missing_fields), 3)
    else:
        completeness = 1.0  # no missing fields expected — full credit

    composite = round((accuracy + grounding + completeness + parse_ok) / 4, 3)

    return StrategyScore(
        strategy=strategy, record_id=record.id,
        accuracy=accuracy, grounding=grounding, completeness=completeness,
        latency_s=latency_s, cost_usd=cost_usd,
        parse_ok=parse_ok, failure=failure, composite=composite,
    )


# ── Strategy 1: Few-Shot Structured Output ─────────────────────────────────────
_FEW_SHOT_SYSTEM = """You are a location services sales and support assistant.
Answer the user query as a JSON object with exactly these fields:
  intent, summary, missing_info (list of strings), recommended_action, confidence (float 0-1)

Examples:

Query: "We want to track 200 trucks across the UK"
Answer: {"intent":"fleet_tracking_qualification","summary":"Customer needs real-time GPS tracking for 200 vehicles in UK","missing_info":["accuracy_requirement","platform","budget","timeline","decision_maker"],"recommended_action":"Qualify accuracy and platform; propose Professional plan at $999/mo for up to 5M calls","confidence":0.85}

Query: "Getting 401 errors on every API call since this morning"
Answer: {"intent":"auth_error_diagnosis","summary":"Authentication failure — token likely expired or revoked","missing_info":["token_type","last_working_timestamp","full_error_response_body"],"recommended_action":"Check JWT expiry (3600s limit); regenerate token in portal; verify X-API-Key header is present","confidence":0.92}

Query: "How does your indoor positioning accuracy compare to others?"
Answer: {"intent":"capability_comparison","summary":"Customer evaluating indoor positioning options against competitors","missing_info":["site_size_sqm","required_accuracy_m","existing_beacon_infrastructure"],"recommended_action":"Highlight BLE 1-3m and UWB 0.1-0.3m accuracy; ask about beacon deployment feasibility and timeline","confidence":0.80}

Now answer this query. Reply with ONLY the JSON object, no explanation:"""


def run_few_shot(query: str, record: Optional[BaselineGTRecord] = None) -> dict:
    llm = get_llm(temperature=0)
    prompt_text = _FEW_SHOT_SYSTEM + "\n" + query
    t0 = time.time()
    failure = None
    raw = ""
    try:
        resp = llm.invoke([SystemMessage(content=_FEW_SHOT_SYSTEM), HumanMessage(content=query)])
        raw = resp.content
        result, failure = _extract_json(raw)
        if failure == "json_fence_wrapping" or (failure and "json" in failure):
            failure = "json_fence_wrapping"
    except Exception as e:
        failure = f"llm_error: {e}"
        result = {"error": str(e), "parse_error": True}

    latency = round(time.time() - t0, 2)
    cost    = _cost(prompt_text, raw)
    score   = _score_result(result, record, latency, cost, failure, "few_shot_structured") if record else None

    return {
        "strategy": "few_shot_structured",
        "result": result,
        "latency_s": latency,
        "cost_usd": cost,
        "failure": failure,
        "score": asdict(score) if score else None,
    }


# ── Strategy 2: Chain-of-Thought with Self-Consistency ────────────────────────
_COT_SYSTEM = """You are a location services assistant. Think step by step.

Step 1 — What is the intent? (sales_qualification / pricing_query / pricing_comparison / capability_query / capability_comparison / limits_comparison / coverage_comparison / error_diagnosis / escalation_required)
Step 2 — What information is explicitly present in the query?
Step 3 — What critical information is missing to give a complete answer?
Step 4 — What does the relevant policy say? (BANT+ for sales; 6-step diagnostic checklist for support)
Step 5 — What is the single best recommended action?

After your reasoning, output ONLY this JSON on the last line:
{"intent":"...","summary":"...","missing_info":[...],"recommended_action":"...","confidence":0.0}"""


def run_cot_self_consistency(query: str, record: Optional[BaselineGTRecord] = None, samples: int = 3) -> dict:
    llm = get_llm(temperature=0.6)
    t0 = time.time()
    responses, failures, raw_texts = [], [], []

    for i in range(samples):
        try:
            resp = llm.invoke([SystemMessage(content=_COT_SYSTEM), HumanMessage(content=query)])
            raw_texts.append(resp.content)
            parsed, fail = _extract_json(resp.content)
            responses.append(parsed)
            if fail:
                failures.append(f"sample_{i}: {fail}")
        except Exception as e:
            failures.append(f"sample_{i}_llm_error: {e}")
            raw_texts.append("")

    valid = [r for r in responses if "intent" in r and not r.get("parse_error")]
    consistency_failure = None
    final: dict = {}

    if not valid:
        consistency_failure = "all_samples_failed_to_parse"
        final = {"error": "no valid samples", "parse_error": True}
    else:
        intents = [r["intent"] for r in valid]
        majority_intent = max(set(intents), key=intents.count)
        agreement = intents.count(majority_intent) / len(intents)
        if agreement < 0.5:
            consistency_failure = "self_consistency_drift"

        all_missing = []
        for r in valid:
            all_missing.extend(r.get("missing_info", []))
        merged_missing = list(dict.fromkeys(all_missing))

        best = next((r for r in valid if r["intent"] == majority_intent), valid[0])
        final = {
            "intent": majority_intent,
            "summary": best.get("summary", ""),
            "missing_info": merged_missing,
            "recommended_action": best.get("recommended_action", ""),
            "confidence": round(sum(r.get("confidence", 0) for r in valid) / len(valid), 2),
            "agreement_rate": round(agreement, 2),
            "samples_used": len(valid),
        }

    all_failures = failures + ([consistency_failure] if consistency_failure else [])
    first_failure = all_failures[0] if all_failures else None
    latency = round(time.time() - t0, 2)
    cost    = _cost(_COT_SYSTEM * samples, " ".join(raw_texts))
    score   = _score_result(final, record, latency, cost, first_failure, "chain_of_thought") if record else None

    return {
        "strategy": "chain_of_thought",
        "result": final,
        "latency_s": latency,
        "cost_usd": cost,
        "failure": first_failure,
        "agreement_rate": round(intents.count(majority_intent) / len(intents), 2) if valid else 0,
        "sample_intents": [r.get("intent", "parse_error") for r in responses],
        "score": asdict(score) if score else None,
    }


# ── Strategy 3: Decomposition Prompting ───────────────────────────────────────
_DECOMP_STEPS = [
    ("intent",
     "Classify the intent of this location services query in 3-5 words using underscores. Reply with ONLY the label."),
    ("present_info",
     "List ONLY the information explicitly stated in this query as a JSON array of strings. No assumptions."),
    ("missing_info",
     "For a location services sales/support team, list the critical missing information needed to respond fully. Reply as a JSON array of strings only."),
    ("policy_check",
     "Does this query require sales qualification (BANT+) or support diagnosis (error checklist)? Reply with one word: 'sales' or 'support'."),
    ("action",
     "What is the single most important next action for the team? One sentence, be specific."),
]

_SYNTHESIS_PROMPT = """Synthesise these sub-answers into a final JSON response.

Sub-answers:
{sub_answers}

Output ONLY this JSON, no explanation:
{{"intent":"...","summary":"...","missing_info":[...],"recommended_action":"...","confidence":0.0}}"""


def run_decomposition(query: str, record: Optional[BaselineGTRecord] = None) -> dict:
    llm = get_llm(temperature=0)
    t0 = time.time()
    sub_answers: dict = {}
    step_failures: list = []
    all_raw = ""

    for step_name, step_prompt in _DECOMP_STEPS:
        try:
            resp = llm.invoke([
                SystemMessage(content=f"You are a location services assistant. {step_prompt}"),
                HumanMessage(content=query),
            ])
            sub_answers[step_name] = resp.content.strip()
            all_raw += resp.content
        except Exception as e:
            sub_answers[step_name] = f"ERROR: {e}"
            step_failures.append(f"{step_name}: {e}")

    synthesis_failure = None
    synthesis_raw = ""
    try:
        synth_prompt = _SYNTHESIS_PROMPT.format(sub_answers=json.dumps(sub_answers, indent=2))
        resp = llm.invoke([HumanMessage(content=synth_prompt)])
        synthesis_raw = resp.content
        all_raw += synthesis_raw
        final, synthesis_failure = _extract_json(synthesis_raw)
    except Exception as e:
        synthesis_failure = f"synthesis_llm_error: {e}"
        final = {"error": str(e), "parse_error": True}

    all_failures = step_failures + ([synthesis_failure] if synthesis_failure else [])
    first_failure = all_failures[0] if all_failures else None
    latency = round(time.time() - t0, 2)
    cost    = _cost(query * len(_DECOMP_STEPS), all_raw)
    score   = _score_result(final, record, latency, cost, first_failure, "decomposition") if record else None

    return {
        "strategy": "decomposition",
        "result": final,
        "sub_answers": sub_answers,
        "latency_s": latency,
        "cost_usd": cost,
        "failure": first_failure,
        "score": asdict(score) if score else None,
    }


# ── Single-query baseline (used by /baseline endpoint) ────────────────────────
def _simple_score(s: dict) -> int:
    r = s.get("result", {})
    return (
        (1 if "intent" in r and not r.get("parse_error") else 0) +
        (1 if isinstance(r.get("missing_info"), list) and len(r["missing_info"]) > 0 else 0) +
        (1 if "recommended_action" in r else 0) +
        (1 if not s.get("failure") else 0)
    )


def run_baseline(query: str, workflow: str = "sales") -> dict:
    """Run all 3 strategies against one query. Used by POST /baseline."""
    few_shot = run_few_shot(query)
    cot      = run_cot_self_consistency(query)
    decomp   = run_decomposition(query)
    strategies = [few_shot, cot, decomp]
    ranked = sorted(strategies, key=_simple_score, reverse=True)
    return {
        "query": query,
        "workflow": workflow,
        "winner": ranked[0]["strategy"],
        "strategies": strategies,
        "comparison_table": [
            {
                "strategy":          s["strategy"],
                "score":             _simple_score(s),
                "latency_s":         s["latency_s"],
                "cost_usd":          s["cost_usd"],
                "intent":            s["result"].get("intent", "—"),
                "missing_info_count": len(s["result"].get("missing_info", [])),
                "has_action":        "recommended_action" in s["result"],
                "failure":           s.get("failure"),
            }
            for s in strategies
        ],
        "failure_modes_catalogue": FAILURE_MODES,
    }
