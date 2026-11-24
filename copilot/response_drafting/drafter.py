# Source history: Deepshikha (f066c61), deepshikha/lbs-copilot. See copilot/enquiry_workflow/source-history.json.
"""Assemble structured responses for draft, clarification, and handoff outcomes."""

from ..enquiry_interpretation.seam import compute_missing_required_fields
from ..safety import escalation_policy


def build_support_output(draft, interpretation, query, comparison=None, *, routing=None):
    team = (interpretation.team if interpretation else None) or "Support"
    policy = routing or escalation_policy.assess(query, None, team.lower())
    owner_team = "Sales" if policy["owner"] == "Account team (Sales)" else "Support"
    if interpretation:
        qualification = interpretation.model_dump(mode="json")["qualification_details"]
    else:
        qualification = dict.fromkeys((
            "use_case_api", "region", "monthly_volume", "current_provider", "timeline",
            "budget", "technical_constraints", "decision_maker",
        ))
        qualification["missing_required_fields"] = compute_missing_required_fields(qualification)
        qualification["complete"] = False
    return {
        "response_draft": draft,
        "clarifying_questions": {"needed": False, "questions": []},
        "qualification_details": qualification,
        "proposed_record_update": {
            "applicable": False, "requires_human_approval": False,
            "approval_status": "not_applicable", "executed": False, "proposal": None,
        },
        "comparison": comparison or {
            "applicable": False, "providers": [], "dimensions": [], "assumptions": [],
            "source_urls": [],
        },
        "responsible_role": {
            "owner": policy["owner"], "team": owner_team, "should_escalate": False,
            "severity": policy["severity"], "reason": routing["reason"] if routing else policy["basis"],
        },
        "next_action": {
            "action_type": "answer_directly", "description": "Review the drafted reply.",
            "requires_human_approval": False, "approval_status": "not_applicable", "executed": False,
        },
    }


def build_terminal_output(interpretation, query, questions, proposals, reason, *, routing=None):
    """Describe the route already chosen, without submitting an action or a draft."""
    proposal = next((item for item in proposals if item["action_type"] == "propose_escalation"), None)
    message = ("\n".join(question["text"] for question in questions["questions"])
               or reason or "Review this enquiry manually.")
    draft = {"draft_text": message, "citations": [], "is_refusal": False, "refusal": None}
    outputs = build_support_output(draft, interpretation, query, routing=routing)
    if questions["needed"]:
        outputs["clarifying_questions"] = questions
        outputs["next_action"].update(action_type="ask_clarifying_questions", description=message)
    elif proposal:
        handoff = proposal["escalation"]
        outputs["responsible_role"].update(
            owner=handoff["owner"], severity=handoff["severity"],
            should_escalate=True, reason=handoff.get("summary") or message,
        )
        outputs["next_action"] = proposal
    else:
        # A fallback needs manual review but has no pending approval to represent.
        draft.update(is_refusal=True, refusal={"policy_id": "manual_review_required", "reason": message})
        outputs["responsible_role"]["reason"] = (
            f"{routing['reason']} {message}"
            if routing and routing["ownership_review"]["provisional"] else message
        )
        outputs["next_action"].update(action_type="refuse", description=message)
    return outputs
