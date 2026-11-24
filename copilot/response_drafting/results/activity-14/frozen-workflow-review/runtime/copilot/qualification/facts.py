"""Merge validated interpretation and explicitly evidenced customer requirements."""
import re
from typing import get_args
from copilot.diagnostics.facts import DiagnosticFact
from .contract import FactId, QualificationContext
from .matrix_facts import validates_quantity
from .extraction import (customer_texts, extract_requirements, requirement_evidence, route_count_proposal,
                         clauses, _customer_clause)
from .workload import (asserted_workload_evidence, normalize_monthly_volume,
                       monthly_volume_proposal, from_text as monthly_volume_from_text, scenario_volume_from_text)
from .task import active_task_sources, task_scope_changed
from .request_scope import request_constraints

FIELDS = set(get_args(FactId))
_STABLE_FIELDS = {'region', 'billing_country', 'current_provider'}


def _active_assertion(fact, enquiry):
    if not fact.evidence:
        return False
    excerpt = fact.evidence.strip().rstrip('.?!;\n').strip()
    for _, text in active_task_sources(enquiry):
        for _, clause, ending in clauses(text):
            if excerpt and excerpt in clause and _customer_clause(clause, ending):
                return True
    return False


def qualification_facts_for_task(state, enquiry):
    """Hide old task requirements while retaining their full audit state."""
    reset = task_scope_changed(enquiry)
    return {field: fact for field, fact in state.facts.items() if field in FIELDS and (
        not reset or field in _STABLE_FIELDS or _active_assertion(fact, enquiry)
    )}


def active_qualification_questions(state, enquiry):
    if not task_scope_changed(enquiry):
        return state.questions
    return [question.model_copy(update={'facts': fields}) for question in state.questions
            if (fields := [field for field in question.facts if field in _STABLE_FIELDS])]


def _monthly_from_sources(enquiry, *, scenario=False):
    parser = scenario_volume_from_text if scenario else monthly_volume_from_text
    for source, text in reversed(active_task_sources(enquiry)):
        if value := parser(text):
            return value, source
    return None, None


def context_from_result(result, state, enquiry):
    interpretation = result['diagnostic_context']['interpretation']
    qualification = result['outputs'].get('qualification_details', {})
    reset = task_scope_changed(enquiry)
    working = state.model_copy(deep=True)
    if reset:
        visible = qualification_facts_for_task(state, enquiry)
        working.facts = {field: fact for field, fact in working.facts.items()
                         if field not in FIELDS or field in visible}
        working.facts.pop('monthly_volume_assumption', None)
        working.questions = active_qualification_questions(state, enquiry)
    _merge_monthly_workload(working, qualification, enquiry)
    for field in FIELDS - {'monthly_volume'}:
        value = qualification.get(field)
        if reset and field not in _STABLE_FIELDS and not _active_assertion(
            DiagnosticFact(field=field, value=value, evidence=str(value) if isinstance(value, (str, int, float)) else ''), enquiry
        ):
            continue
        if value is not None and not (field in working.facts and working.facts[field].status == 'supplied'):
            working.facts[field] = DiagnosticFact(field=field, value=value, source='interpretation',
                                                 evidence=f'qualification_details.{field}')
    previous_stops = working.facts.get('max_stops')
    if previous_stops and previous_stops.status == 'supplied' and (previous_stops.source == 'query' or previous_stops.source.startswith('history[')):
        context = requirement_evidence(enquiry, previous_stops.evidence)
        if not context or not route_count_proposal(previous_stops.value, context[1]):
            working.facts['max_stops'] = previous_stops.model_copy(update={'status': 'missing'})
    for source, text in active_task_sources(enquiry):
        for proposal in extract_requirements({'query': text}):
            working.facts[proposal['field']] = DiagnosticFact(**{**proposal, 'source': source})
        for match in re.finditer(r'(?i:\b(?:shown|displayed|instructions|returned)\s+in)\s+([A-Z][A-Za-z-]*(?:,\s*[A-Z][A-Za-z-]*)*(?:\s+and\s+[A-Z][A-Za-z-]*)?)', text):
            if not requirement_evidence({'query':text}, match.group()):
                continue
            working.facts['languages'] = DiagnosticFact(field='languages', value=match.group(1), source=source,
                evidence=match.group(), start=match.start(), end=match.end())
    traffic = working.facts.get('traffic_required')
    if traffic and traffic.status == 'supplied' and traffic.value is True and re.search(r'\blive[- ]traffic\b', traffic.evidence, re.I):
        working.facts['traffic_conditions'] = traffic.model_copy(update={'field': 'traffic_conditions', 'value': 'live'})
    for question in working.questions:
        if question.status == 'asked' and all(working.facts.get(f) and working.facts[f].status == 'supplied' for f in question.facts):
            question.status = 'answered'
    # Earlier task facts stay in the audit state; only current requirements enter the context.
    state.facts.update(working.facts)
    for question in working.questions:
        for stored in state.questions:
            if stored.facts == question.facts and stored.text == question.text:
                stored.status = question.status
    return QualificationContext(api=interpretation['api'], intent=interpretation['intent'],
        facts={field: fact for field, fact in working.facts.items() if field in FIELDS},
        assumptions={**({'monthly_volume': working.facts['monthly_volume_assumption']}
            if 'monthly_volume_assumption' in working.facts else {}), **request_constraints(enquiry)},
        blocked_fields=sorted({field for question in working.questions if question.status in {'asked', 'declined'}
                               for field in question.facts if field in FIELDS}),
        missing_interpretation_fields=qualification.get('missing_required_fields', []))


def merge_model_facts(state, plan, enquiry):
    sources = active_task_sources(enquiry)
    source_order = {source: index for index, (source, _) in enumerate(sources)}
    boolean_fields = {'storage_required','traffic_required','details_completion','debouncing',
        'session_tokens','api_enabled','existing_project','hazmat_required','requests_splittable',
        'redistribution_required','resale_required','address_elements_required','rooftop_hard_filter',
        'public_service_acceptable','temporary_results_acceptable','mapbox_traffic_profile','ola_contract','poi_required'}
    for proposal in plan.supplied_facts:
        if not proposal.evidence.strip():
            continue
        assertion = _proposal_assertion(enquiry, proposal, state)
        if not assertion or assertion[0] not in source_order:
            continue
        if isinstance(proposal.value, bool) and proposal.field not in boolean_fields:
            continue
        if proposal.field == 'monthly_volume':
            source = next((source for source,text in reversed(sources) if proposal.evidence in text),None)
            text = dict(sources).get(source, '')
            value = monthly_volume_proposal(proposal.value, proposal.evidence) if source and asserted_workload_evidence(text, proposal.evidence) else None
            latest, latest_source = _monthly_from_sources(enquiry)
            if value and latest and source == latest_source and all(
                value[key] == latest[key] for key in ('requests_per_month', 'unit')
            ):
                state.facts['monthly_volume'] = DiagnosticFact(field='monthly_volume',value=latest,
                    source=latest_source,evidence=latest['raw'])
            continue
        source = assertion[0]
        if proposal.field in {'storage_required','traffic_required','details_completion','debouncing',
            'session_tokens','api_enabled','existing_project','hazmat_required','requests_splittable',
            'redistribution_required','resale_required','address_elements_required','rooftop_hard_filter',
            'public_service_acceptable','temporary_results_acceptable','mapbox_traffic_profile','ola_contract','poi_required'}:
            evidence = assertion[1]
            if not _boolean_evidence(proposal.field, proposal.value, evidence) or re.search(r'\b(?:may|might|possibly|optionally)\b', proposal.evidence, re.I):
                continue
        if not isinstance(proposal.value, bool) and not _literal_or_alias(proposal.field, proposal.value, proposal.evidence):
            continue
        previous = qualification_facts_for_task(state, enquiry).get(proposal.field)
        if previous and previous.status == 'supplied' and previous.value is not None:
            if previous.source == 'interpretation':
                continue
            # A saved model fact can still say "query" after its turn becomes history.
            previous_source = next((name for name, text in reversed(sources)
                                    if previous.evidence and previous.evidence in text), None)
            if previous_source is None:
                if source != 'query':
                    continue
            elif source_order[source] <= source_order[previous_source]:
                continue
        state.facts[proposal.field] = DiagnosticFact(field=proposal.field, value=proposal.value,
                                                    source=source, evidence=proposal.evidence)


def _proposal_assertion(enquiry, proposal, state):
    """Bind the proposed value inside both its quoted range and an asserted clause."""
    for source, text in reversed(customer_texts(enquiry)):
        for quoted in re.finditer(re.escape(proposal.evidence), text):
            for offset, clause, ending in clauses(text):
                left, right = max(quoted.start(), offset), min(quoted.end(), offset + len(clause))
                asserted = _customer_clause(clause, ending)
                if not asserted and re.match(r'\s*do not\b', clause, re.I) and re.search(r'\band\s*$', text[:offset], re.I):
                    preceding = re.split(r'[.!?;\n]', text[:offset])[-1]
                    # An affirmative customer sentence can share its subject across "and".
                    asserted = bool(re.match(r'\s*(?:we|I)\b', preceding, re.I)
                                    and _customer_clause(preceding, '') and _customer_clause('We ' + clause.lstrip(), ending))
                if left >= right or not asserted:
                    continue
                excerpt = text[left:right]
                if isinstance(proposal.value, bool):
                    anchor = _BOOL_ANCHORS.get(proposal.field)
                    valid = bool(anchor and re.search(anchor, excerpt, re.I)
                                 and _boolean_evidence(proposal.field, proposal.value, clause))
                else:
                    valid = (_literal_or_alias(proposal.field, proposal.value, excerpt)
                             and _non_boolean_assertion(proposal, clause, excerpt, state))
                if valid and (proposal.field != 'max_stops' or (
                    route_count_proposal(proposal.value, clause) and route_count_proposal(proposal.value, excerpt)
                )):
                    return source, clause
    return None


_COUNT_CONTEXT = {
    'origin_count': r'\borigins?\b', 'destination_count': r'\bdestinations?\b',
    'matrix_frequency': r'\bmatri(?:x|ces)\b',
    'peak_concurrency': r'\b(?:concurrent|concurrency|simultaneous)\b',
    'peak_rate': r'\b(?:rps|requests?\s*(?:per|/)\s*second|peak\s+rate)\b',
}


def _non_boolean_assertion(proposal, clause, excerpt, state):
    if not validates_quantity(proposal.field, proposal.value, clause):
        return False
    raw = str(proposal.value)
    numeric = re.fullmatch(r'\d[\d,]*(?:\.\d+)?', raw)
    if numeric:
        expected = float(raw.replace(',', ''))
        tokens = re.findall(r'(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w.])', excerpt)
        if not any(float(token.replace(',', '')) == expected for token in tokens):
            return False
        anchor = _COUNT_CONTEXT.get(proposal.field)
        answered = any(proposal.field in question.facts and question.status == 'asked' for question in state.questions)
        if anchor and not re.search(anchor, clause, re.I) and not answered:
            return False
    value_match = re.search(r'(?<!\w)' + re.escape(raw) + r'(?!\w)', clause, re.I)
    if value_match is None:
        alias = _ALIASES.get(proposal.field, {}).get(raw.casefold())
        value_match = re.search(alias, clause, re.I) if alias else None
    if value_match and re.search(r"\b(?:not|never|without|don't|doesn't|won't)\b", clause[:value_match.start()], re.I):
        return False
    return True


_BOOL_ANCHORS = {
    'ola_contract':r'Ola.{0,40}contract|contract.{0,40}Ola',
    'poi_required':r'\bPOIs?\b|points? of interest',
    'details_completion':r'place details|\bretrieve\b|details? calls?',
    'debouncing':r'debounc|throttl|stops? typing|typing (?:has )?stopped',
    'storage_required':r'stor|retain|cache|sav(?:e|ing)',
    'traffic_required':r'traffic|live ETA',
    'session_tokens':r'session.?token', 'api_enabled':r'enabl|disabl',
    'existing_project':r'(?:existing|new|current|enabled) (?:Google )?(?:Cloud )?project',
    'hazmat_required':r'hazmat|hazardous', 'requests_splittable':r'split|batch',
    'redistribution_required':r'redistribut', 'resale_required':r'resell|resale',
    'address_elements_required':r'address.{0,25}(?:elements|components|breakdown)|broken into elements',
    'rooftop_hard_filter':r'only.{0,180}rooftop|rooftop.{0,30}(?:only|hard|filter)|hard filter',
    'public_service_acceptable':r'public.{0,35}(?:acceptable|accept|okay|ok)|(?:accept|use).{0,30}public',
    'temporary_results_acceptable':r'temporary.{0,35}(?:acceptable|accept|okay|ok)|(?:accept|use).{0,30}temporary',
    'mapbox_traffic_profile':r'driving-traffic',
}


def _boolean_evidence(field, value, evidence):
    if not isinstance(value, bool) or not re.search(_BOOL_ANCHORS[field], evidence, re.I):
        return False
    if re.search(r'with and without|either.{0,30}or', evidence, re.I):
        return False
    negative = bool(re.search(r"\b(?:no|not|never|without|cannot|can't|don't|doesn't|won't|haven't|didn't)\b", evidence, re.I))
    if field == 'existing_project' and re.search(r'\bnew\s+(?:Google )?(?:Cloud )?project\b', evidence, re.I):
        negative = True
    return not negative if value else negative


_ALIASES = {
    'instruction_modality': {'voice':r'\bspoken|\baudio|\btts\b', 'text':r'\bwritten\b'},
    'lookup_trigger': {'user-triggered':r'\bmanual|\bon demand|\buser.initiated|\bclick',
                       'periodic':r'\bperiodic|\bscheduled|\bpolling'},
}


def _literal_or_alias(field, value, evidence):
    normalized = lambda text: re.sub(r'[^a-z0-9]', '', str(text).casefold())
    if normalized(value) in {'unknown','unspecified','notspecified','notprovided','na'}:
        return False
    if normalized(value) and normalized(value) in normalized(evidence):
        return True
    pattern=_ALIASES.get(field,{}).get(str(value).casefold())
    return bool(pattern and re.search(pattern,evidence,re.I))


def _merge_monthly_workload(state, qualification, enquiry):
    previous=state.facts.get('monthly_volume')
    explicit,source=_monthly_from_sources(enquiry)
    scenario, scenario_source = _monthly_from_sources(enquiry, scenario=True)
    volume = qualification.get('monthly_volume')
    if task_scope_changed(enquiry) and volume is not None and not _active_assertion(
        DiagnosticFact(field='monthly_volume', value=volume,
                       evidence=volume.get('raw', '') if isinstance(volume, dict) else str(volume)), enquiry
    ):
        volume = None
    if scenario:
        state.facts['monthly_volume_assumption'] = DiagnosticFact(field='monthly_volume_assumption',
            value=scenario,source=scenario_source,evidence=scenario['evidence'])
    else:
        state.facts.pop('monthly_volume_assumption', None)
    if explicit:
        state.facts['monthly_volume']=DiagnosticFact(field='monthly_volume',value=explicit,
            source=source,evidence=explicit['raw'])
    elif previous and previous.status == 'supplied' and previous.source == 'state_store' and not previous.evidence and (
        normalized := normalize_monthly_volume(previous.value)
    ):
        # A typed external case fact can be trusted without inventing a customer quote.
        state.facts['monthly_volume'] = previous.model_copy(update={'value': normalized})
    elif previous or volume is not None:
        # Partial quantities stay visible but cannot suppress the workload question.
        state.facts['monthly_volume']=DiagnosticFact(field='monthly_volume',status=previous.status if previous and previous.status in {'asked','declined'} else 'missing',
            value=volume if volume is not None else previous.value,
            source='qualification_normalization',evidence='Monthly API quantity and workload unit are not both confirmed.')
