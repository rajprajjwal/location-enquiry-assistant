"""Classify the work needed when the customer relationship is unconfirmed."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProvisionalAssignment:
    task: str
    team: str
    reason: str


def provisional_assignment(message, interpretation):
    """Apply the approved task policy without inferring new or existing status."""
    text = message.lower()
    intent = interpretation.intent
    if re.search(r'\b(?:licen[cs]\w*|resell\w*|redistribut\w*|commercial use|permanent storage|store\b.{0,65}\b(?:database|reuse))\b', text):
        return ProvisionalAssignment('licensing_decision', 'sales', 'Licensing or reuse permission needs provisional commercial ownership.')
    if re.search(r'\b(?:custom|bespoke|enterprise) (?:quote|pricing|plan)|\b(?:negotiat\w*|overcharg\w*|billing discrepancy|billing policy|billing review|refund|dispute)\b', text):
        return ProvisionalAssignment('billing_policy', 'sales', 'Account terms or billing-policy decisions need Sales ownership.')
    if intent == 'troubleshooting':
        return ProvisionalAssignment('troubleshooting', 'support', 'Troubleshooting needs provisional technical support.')
    selection = re.search(r'\b(?:which|what|any|who)\b.{0,120}\b(?:apis|providers|vendors|geocoders|options|services)\b', text, re.S)
    if intent in {'pricing_quote', 'pricing_comparison'}:
        if re.search(r'\bquotes?\b|\b(?:plan\w* to|want to launch|we expect|we anticipate|forecast|rollout|deployment)\b', text):
            return ProvisionalAssignment('deployment_quote', 'sales', 'A deployment quote or planned rollout needs provisional Sales qualification.')
        if selection and not re.search(r'\b(?:calculat\w*|list prices?|published (?:rates?|prices?)|free allowance|\d[\d,]*\s+(?:elements|requests|lookups|calls))\b', text):
            return ProvisionalAssignment('product_selection', 'sales', 'Choosing provider options needs provisional Sales qualification.')
        if re.search(r'\b(?:cost|price|pricing|charge|free|billed|bill|rate|usd|inr|elements|requests)\b', text):
            return ProvisionalAssignment('published_rate_calculation', 'support', 'Published-rate calculations and billing mechanics need provisional Support ownership.')
        return ProvisionalAssignment('product_selection', 'sales', 'Comparing product variants needs provisional Sales qualification.')
    if selection or intent in {'capability_match', 'sales_qualification'}:
        return ProvisionalAssignment('product_selection', 'sales', 'Product or provider selection needs provisional Sales qualification.')
    return ProvisionalAssignment('api_documentation', 'support', 'API documentation and published service behavior need provisional Support ownership.')
