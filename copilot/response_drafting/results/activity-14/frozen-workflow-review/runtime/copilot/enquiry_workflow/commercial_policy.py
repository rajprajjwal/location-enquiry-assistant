"""Recognize explicit commercial decisions without inferring customer status."""
import re

_RIGHTS = re.compile(r'\b(?:licen[cs](?:e|ing) obligations|resell\w*|redistribution rights|commercial reuse)\b', re.I)
_QUOTE = re.compile(r'\bquot(?:e|es|ation)\b', re.I)
_NO_QUOTE = re.compile(r'\b(?:not|never|no)\b.{0,30}\bquot(?:e|es|ation)\b', re.I)


def commercial_policy_reason(context, interpretation):
    """Only explicit rights decisions and quote requests have this policy priority."""
    if _RIGHTS.search(context):
        return 'Licensing obligations or commercial reuse require provisional Sales ownership.'
    if interpretation.intent == 'pricing_quote' and _QUOTE.search(context) and not _NO_QUOTE.search(context):
        return 'The customer requested a deployment quote; Sales ownership is provisional until the relationship is confirmed.'
    return None
