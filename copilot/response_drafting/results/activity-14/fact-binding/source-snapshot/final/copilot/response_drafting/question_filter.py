"""Reject staff questions that request secrets or delegate documentation lookup."""
import re


_SECRET = re.compile(
    r"\b(?:api[ _-]?key|access[ _-]?token|oauth[ _-]?token|bearer[ _-]?token|client[ _-]?secret|password|credentials|authorization header)\b",
    re.I,
)
_REQUEST = re.compile(r"\b(?:what|which|share|provide|send|paste|give|show|enter|tell)\b", re.I)
_REDACTION = re.compile(r"\b(?:redact\w*|remov\w*|omit\w*|mask\w*|without|exclude\w*)\b", re.I)
_SECRET_METADATA = re.compile(r"^\s*(?:restrictions?|status|type|configuration|permissions?|scopes?)\b", re.I)
_CUSTOMER_EVIDENCE = re.compile(
    r"\b(?:exact|example|sample|failing|redacted)\b.{0,45}\b(?:request|response|input|output|coordinates|origin|destination)\b"
    r"|\b(?:request|response)\s+(?:body|payload|path|URL)\b"
    r"|\b(?:what|which|share|provide)\b.{0,55}\b(?:coordinates|latitude|longitude|origin and destination|result filters)\b"
    r"|\b(?:on (?:its|their) own|sent alone|raw (?:API )?response)\b"
    r"|\b(?:did|do|have|were)\s+you\b.{0,45}\b(?:observe\w*|send|sent|receive\w*|measure\w*|configure\w*)\b"
    r"|\byour\b.{0,40}\b(?:observed|measured|configured)\b", re.I,
)
_DOCUMENTATION = re.compile(
    r"\b(?:documentation|documented|default|maximum|supported|allowed)\b"
    r"|\b(?:exact keys|response structure|response format|structure of .{0,60}response)\b"
    r"|\b(?:does|can)\b.{0,100}\b(?:API|Search Box)\b.{0,90}\b(?:allow|support|limit|specif)"
    r"|\b(?:required|correct)\b.{0,50}\b(?:User-Agent|output format|parameters|format)\b"
    r"|\bformat\b.{0,60}\bsupports?\b", re.I,
)
_CONFIGURATION_ADVICE = re.compile(
    r"\b(?:is|are)\b.{0,60}\b(?:API key|User-Agent|parameters)\b.{0,80}\b(?:active|correct|configur|valid)"
    r"|\b(?:can you configure|are you required|are you configured to)\b", re.I,
)


def question_rejection(text, *, customer_requirement=False):
    """Keep customer evidence requests. Return an explicit rejection reason."""
    for clause in re.split(r"[?.!]", text):
        for secret in _SECRET.finditer(clause):
            before, after = clause[:secret.start()], clause[secret.end():]
            if re.search(r"\b(?:do not|don't|never)\s+(?:share|send|provide|paste|include|reveal)\b", before, re.I):
                continue
            if _SECRET_METADATA.search(after):
                continue
            if re.search(r"\b(?:restrictions?|scopes?|permissions?|type|status|expiry|expiration)\s+of\s+(?:the\s+)?$", before, re.I):
                continue
            # A redaction instruction is allowed only for this named secret.
            if (_REDACTION.search(before[-35:]) or
                    re.match(r"\s+(?:(?:value|values)\s+)?(?:redacted|removed|omitted|masked)\b", after, re.I)):
                continue
            if _REQUEST.search(before):
                return "credential_value_requested"
    # Validated requirement fields describe customer needs, not provider documentation.
    if customer_requirement:
        return None
    if _CUSTOMER_EVIDENCE.search(text):
        return None
    if _DOCUMENTATION.search(text):
        return "documentation_question"
    # Configuration checklists can be given in a draft without asking the customer to confirm them.
    if _CONFIGURATION_ADVICE.search(text):
        return "configuration_advice_as_question"
    return None
