# Source history: Raj Kumar (a3ef3a6); see source-history.json.
from langchain_core.messages import SystemMessage, HumanMessage
from app.llm import get_llm
from app.agents.json_utils import invoke_json
import json

CRITIC_SYSTEM = """You are a Location Services Copilot Critic.
Review the drafted response against the provided knowledge base sources.

Check:
1. GROUNDING: Every factual claim must be supported by a source. Flag unsupported claims.
2. COMPLETENESS: Are all planner-identified missing fields addressed?
3. ACCURACY: Are numbers, limits, formats, and error codes correct per sources?
4. ESCALATION: Is the escalation recommendation appropriate per policy?
5. HANDOFF: If a handoff is proposed, are requirements, findings, and open questions included?

Respond ONLY with valid JSON:
{
  "approved": true,
  "confidence": 0.95,
  "issues": [],
  "unsupported_claims": [],
  "suggested_revision": ""
}

If approved is false, provide suggested_revision with the corrected response text.
"""


def run_critic(draft_response: str, sources: list[dict], planner_output: dict) -> dict:
    llm = get_llm(temperature=0)
    sources_text = "\n".join(f"[KB-{i+1}] {s['content']}" for i, s in enumerate(sources))
    prompt = f"""Draft response:
{draft_response}

Sources used:
{sources_text}

Planner output:
{json.dumps(planner_output)}"""

    messages = [SystemMessage(content=CRITIC_SYSTEM), HumanMessage(content=prompt)]
    result, _ = invoke_json(llm, messages, fallback={
        "approved": True, "confidence": 0.7, "issues": [], "unsupported_claims": [], "suggested_revision": ""
    })
    return result
