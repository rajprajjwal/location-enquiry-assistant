# Source history: Deepshikha (62db1b2), deepshikha/lbs-copilot. See copilot/enquiry_workflow/source-history.json.
"""Escalation policy SC-02: severity and owning team for an escalation category (config/escalation_policy.yaml).

The rules in escalation.py decide WHETHER and WHY to escalate (category + evidence to collect); this module adds HOW URGENT (SEV1-4) and
WHICH TEAM owns it, from the approved policy. Pure and deterministic; nothing is sent or applied (a human still approves every escalation).
"""
from copilot.paths import CONFIG_DIR
import re
from functools import lru_cache

import yaml

_CFG = CONFIG_DIR / "escalation_policy.yaml"


@lru_cache(maxsize=1)
def policy() -> dict:
    return yaml.safe_load(_CFG.read_text(encoding="utf-8"))


def version() -> str:
    return policy()["policy_version"]


def assess(message: str, category: str | None, workflow: str | None = None) -> dict:
    """-> {severity, owner, policy_version, basis}. `category` is an escalation category (production_incident, security_incident, ...); for an
    ordinary (non-escalating) case pass category=None and the workflow ("support" | "sales")."""
    p = policy()
    if category in p["categories"]:
        spec = p["categories"][category]
        for rule in spec.get("rules", []):
            if re.search(rule["when"], message, re.I):
                out = dict(rule["then"])
                if rule.get("upgrade_when") and re.search(rule["upgrade_when"], message, re.I):
                    out["severity"] = rule["upgrade_to"]
                return {**out, "policy_version": version(), "basis": f"{category}: rule /{rule['when'][:40]}/"}
        return {**spec["default"], "policy_version": version(), "basis": f"{category}: default"}
    base = p["non_escalating"].get("sales" if workflow == "sales" else "support")
    return {**base, "policy_version": version(), "basis": f"no escalation ({workflow or 'support'})"}

def customer_status(message: str) -> str:
    """Resolve asserted customer status and observed service-use evidence."""
    from .customer_evidence import customer_status as resolve_status

    config = policy()
    return resolve_status(message, config["customer_status"],
                          actual_use=config.get("actual_use_detection", False))


def routine_owner(message, interpretation, *, provider_count: int = 0,
                  customer_status_override: str | None = None) -> dict:
    """Resolve routine ownership from ordered rules, then use the interpreted team."""
    defaults = policy()["non_escalating"]
    status = customer_status_override or customer_status(message)
    routine_intents = {"pricing_quote", "pricing_comparison", "capability_match", "coverage_limits",
                       "sales_qualification", "docs_how_to", "troubleshooting"}
    commercial = re.search(
        r"\b(?:custom|bespoke|enterprise) (?:quote|pricing|discount|plan)\b"
        r"|\b(?:overcharg\w*|billing discrepancy|negotiat\w*)\b", message, re.I,
    )
    if interpretation.intent in routine_intents and status != "unknown" and not commercial:
        team = "support" if status == "existing" else "sales"
        reason = ("An existing customer needs service guidance."
                  if status == "existing" else "A new customer needs sales qualification.")
        return {**defaults[team], "basis": reason}
    if (status == "unknown" and policy().get("provider_discovery_fallback", False)
            and interpretation.intent in {"capability_match", "coverage_limits", "pricing_comparison", "sales_qualification"}
            and re.search(r"\b(?:which|what|any)\b.{0,85}\b(?:providers?|APIs|geocoders|options|services)\b"
                          r"|\bwho covers\b", message, re.I | re.S)
            and not re.search(r"\b(?:one call|single call|per request|fewest|maximum|limit|batch)\b", message, re.I)):
        return {**defaults["sales"], "basis": "Provider discovery needs provisional sales qualification."}
    for rule in policy().get("routine_ownership", []):
        if provider_count < rule.get("min_providers", 0):
            continue
        pattern = rule.get("when")
        required = rule.get("and_when")
        excluded = rule.get("not_when")
        if excluded and re.search(excluded, message, re.I | re.S):
            continue
        if required and not re.search(required, message, re.I | re.S):
            continue
        if (interpretation.intent in rule.get("intents", [])
                or interpretation.sub_intent in rule.get("sub_intents", [])
                or (pattern and re.search(pattern, message, re.I | re.S))):
            return {**defaults[rule["team"]], "basis": rule["reason"]}
    return assess(message, None, (interpretation.team or "Support").lower())
