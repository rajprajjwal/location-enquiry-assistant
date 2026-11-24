"""Keep explicitly requested answer options separate from actual customer usage."""
import re

from copilot.diagnostics.facts import DiagnosticFact
from copilot.enquiry_workflow.routing import customer_question, asks_qualification
from copilot.safety.provider_evidence import provider_mentions
from .task import active_task_sources
from .extraction import storage_requirements, details_requirements, travel_requirements

_REQUEST = re.compile(r'^\s*(?:(?:actually|correction)[,:]?\s*)?(?:what|which|how|why|when|where|can|could|should|would|do|does|is|are|'
                      r'(?:please\s+)?(?:compare|recommend|explain|describe|show|tell|calculate|estimate|use|assume))\b', re.I)
_COMPARE = re.compile(r'\b(?:compare|versus|vs|either|both|or|differences?|pros|cons)\b', re.I)
_NEGATED = re.compile(r"\b(?:not(?!\s+only\b)|never|without|don't|do not)\b", re.I)
_MODALITIES = {'text': 'text', 'written': 'text', 'textual': 'text',
               'voice': 'voice', 'spoken': 'voice', 'audio': 'voice'}
_MODALITY = re.compile(r'\b(?:text|written|textual|voice|spoken|audio)\b', re.I)
_INSTRUCTIONS = re.compile(r'\b(?:instructions?|guidance|navigation|turn[- ]by[- ]turn)\b', re.I)
_FUTURE = re.compile(r'\bfuture\s+(?:departure(?:[- ]times?)?s?|traffic|ETAs?)\b|'
                     r'\bdeparture(?:[-_ ]time)?\s*(?:for|at|in)\s+the future\b', re.I)
_NOW = re.compile(r'\b(?:current|immediate)\s+(?:departure(?:[- ]times?)?s?|traffic|ETAs?)\b|'
                  r'\bdeparture[_ -]?time\s*[:=]\s*now\b|\bdepart(?:ing|ure)?\s+now\b', re.I)
_HOSTING = {
    'self-hosted': re.compile(r'\bself[- ]host(?:ed|ing)?\b', re.I),
    'managed': re.compile(r'(?<![\w-])(?:managed|hosted)\s+(?:API|service|endpoint|provider|solution)\b', re.I),
}
_ESTIMATE_SCOPE = re.compile(r'\b(?:compare|versus|vs|cost|prices?|pricing|quote|estimate|bill\w*|charg\w*|pay|options?|cheaper)\b', re.I)
_UNDECIDED = re.compile(r'\b(?:may|might|maybe|possibly|perhaps|whether|not sure|undecided)\b', re.I)
_DOC_STATEMENT = re.compile(r'\b(?:docs?|documentation|manual|pricing page)\b.{0,50}\b(?:says?|states?|requires?|examples?|shows?)\b', re.I)
_FINAL_DETAILS = re.compile(r'\b(?:final|terminating)\s+Place\s+Details(?:\s+(?:Essentials|Pro|Enterprise))?\s+(?:call|request)\b', re.I)


def _requested_clauses(enquiry):
    for source, raw in active_task_sources(enquiry):
        body = customer_question(raw)
        body_offset = raw.find(body)
        for match in re.finditer(r'[^.!?;\n]+[.!?;]?', body):
            clause = match.group()
            if not asks_qualification(clause) and ('?' in clause or _REQUEST.search(clause)):
                yield source, raw, body_offset + match.start(), clause


def _positive(match, clause):
    # An explicitly excluded option is not the requested answer scope.
    return not _NEGATED.search(clause[max(0, match.start() - 25):match.start()])


def _instruction_option(mode, instructions, clause):
    for instruction in instructions:
        if mode.end() <= instruction.start():
            bridge = clause[mode.end():instruction.start()]
            if re.fullmatch(r'\s*(?:(?:and|or|versus|vs|for|/|voice|spoken|audio|text|written|textual|turn-by-turn|route|navigation)\s+)*', bridge, re.I):
                return True
        elif instruction.end() <= mode.start():
            bridge = clause[instruction.end():mode.start()]
            if re.fullmatch(r'\s*(?:(?:must|should|can|could|will|would|are|be|is|returned|provided|delivered|generated|available|supported|support|as|in|using|with|via|only|either|both|or|and|the|form|of|voice|spoken|audio|text|written|textual)\s+)*', bridge, re.I):
                return True
    return bool(re.search(r'\b' + re.escape(mode.group()) + r'\s+directions\b', clause, re.I))


def request_constraints(enquiry):
    """Return exact-evidenced requested options, never asserted operational facts."""
    assumptions = {}
    for source, raw, offset, clause in _requested_clauses(enquiry):
        def add(field, value, start, end):
            evidence = clause[start:end]
            assumptions[field] = DiagnosticFact(field=field, source=source,
                value={'value': value, 'basis': 'requested_scope', 'evidence': evidence},
                evidence=evidence, start=offset + start, end=offset + end)

        modes = [match for match in _MODALITY.finditer(clause) if _positive(match, clause)]
        instructions = list(_INSTRUCTIONS.finditer(clause))
        modes = [match for match in modes if _instruction_option(match, instructions, clause)]
        values = list(dict.fromkeys(_MODALITIES[match.group().casefold()] for match in modes))
        if len(values) == 1 or len(values) > 1 and _COMPARE.search(clause):
            add('instruction_modality', values[0] if len(values) == 1 else values,
                modes[0].start(), modes[-1].end())

        future = next((match for match in _FUTURE.finditer(clause) if _positive(match, clause)), None)
        now = next((match for match in _NOW.finditer(clause) if _positive(match, clause)), None)
        if future and not now and _COMPARE.search(clause):
            now = re.search(r'\bnow\b', clause, re.I)
        if now and future:
            add('departure_time_mode', ['now', 'future'], min(now.start(), future.start()), max(now.end(), future.end()))
        elif future or now:
            match = future or now
            add('departure_time_mode', 'future' if future else 'now', match.start(), match.end())

        hosting = [(value, match) for value, pattern in _HOSTING.items()
                   for match in pattern.finditer(clause) if _positive(match, clause)]
        hosting.sort(key=lambda item: item[1].start())
        values = list(dict.fromkeys(value for value, _ in hosting))
        if len(values) == 1 or len(values) > 1 and _COMPARE.search(clause):
            add('hosting_preference', values[0] if len(values) == 1 else values,
                hosting[0][1].start(), hosting[-1][1].end())

        providers = provider_mentions(clause)
        if len(providers) >= 2 and _COMPARE.search(clause):
            add('alternative_providers', [provider['value'] for provider in providers],
                providers[0]['start'], providers[-1]['end'])
        if _ESTIMATE_SCOPE.search(clause) and not _DOC_STATEMENT.search(clause):
            for value, match in storage_requirements(clause, requested=True):
                if not _UNDECIDED.search(clause[max(0, match.start() - 45):match.end()]):
                    add('storage_required', value, match.start(), match.end())
            for field, value, match in details_requirements(clause):
                if not _UNDECIDED.search(clause[max(0, match.start() - 45):match.end()]):
                    add(field, value, match.start(), match.end())
            final = _FINAL_DETAILS.search(clause)
            if final and _positive(final, clause) and re.search(r'\bautocomplete\b', clause, re.I):
                between = clause[:final.start()]
                if re.search(r'\band\s+(?:the\s+|our\s+)?$', between, re.I):
                    add('details_completion', True, final.start(), final.end())
            for mode, match in travel_requirements(clause):
                if _positive(match, clause) and not _UNDECIDED.search(clause[max(0, match.start() - 45):match.end()]):
                    add('travel_mode', mode, match.start(), match.end())
        geographic = []
        for value, pattern in (
            ('hard_restriction', r'\b(?:hard|strict(?:ly)?)\s+(?:geographic\s+)?(?:restrict\w*|filter\w*|bound\w*)\b'),
            ('bias', r'\b(?:(?:location|geographic|proximity)\s+)?bias\b'),
        ):
            for match in re.finditer(pattern, clause, re.I):
                if _positive(match, clause):
                    geographic.append((value, match))
        if geographic:
            values = list(dict.fromkeys(value for value, _ in geographic))
            add('geographic_matching', values[0] if len(values) == 1 else values,
                min(match.start() for _, match in geographic), max(match.end() for _, match in geographic))
    return assumptions
