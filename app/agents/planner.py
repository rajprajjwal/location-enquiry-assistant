from langchain.schema import SystemMessage, HumanMessage
from app.llm import get_llm
from app.agents.json_utils import invoke_json
import json

SALES_SYSTEM = """You are a Sales Copilot Planner for a location services company.
Your job:
1. Identify missing qualification fields (use case, device count, accuracy, platform, budget, timeline, decision-maker, compliance).
2. Classify the enquiry type (capability_match, pricing, integration, qualification, communication_prep).
3. Propose targeted discovery questions for missing fields.
4. Propose ownership and next actions.
5. Check if escalation to Solutions Engineer is needed (custom integration, <1m accuracy, >10k devices, compliance).

Respond ONLY with valid JSON:
{
  "enquiry_type": "...",
  "missing_fields": [...],
  "discovery_questions": [...],
  "next_actions": [...],
  "escalation_needed": false,
  "escalation_reason": "..."
}"""

SUPPORT_SYSTEM = """You are a Support Copilot Planner for a location services company.
Your job:
1. Classify the issue (auth, coordinates, quota, device_config, rate_limit, service_availability, integration).
2. Identify missing diagnostic info (device_id, error_code, timestamp, request_params, error_response_body).
3. Select diagnostic steps appropriate to the issue type.
4. Apply escalation policy: escalate if error rate >5% for >15min, data loss suspected, security incident, or L2 unresolved >4h.
5. Propose ownership and next actions.

Respond ONLY with valid JSON:
{
  "issue_category": "...",
  "missing_info": [...],
  "diagnostic_steps": [...],
  "next_actions": [...],
  "escalation_needed": false,
  "escalation_reason": "..."
}"""


def run_planner(workflow: str, user_message: str, history: list[dict], tracker_summary: dict) -> dict:
    llm = get_llm(temperature=0)
    system = SALES_SYSTEM if workflow == "sales" else SUPPORT_SYSTEM
    context = f"Tracker state: {json.dumps(tracker_summary)}\n\nConversation history summary: {_summarise_history(history)}"
    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"{context}\n\nLatest message: {user_message}"),
    ]
    result, _ = invoke_json(llm, messages, fallback=lambda raw: {"raw": raw, "parse_error": True})
    return result


def _summarise_history(history: list[dict]) -> str:
    if not history:
        return "No prior history."
    lines = [f"{m['role'].upper()}: {m['content'][:200]}" for m in history[-6:]]
    return "\n".join(lines)
