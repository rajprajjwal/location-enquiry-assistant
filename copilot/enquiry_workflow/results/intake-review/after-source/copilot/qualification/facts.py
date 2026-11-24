"""Merge validated interpretation and explicitly evidenced customer requirements."""
import re
from typing import get_args
from copilot.diagnostics.facts import DiagnosticFact
from .contract import FactId, QualificationContext
from .extraction import customer_texts, extract_requirements, requirement_evidence, route_count_proposal
from .workload import (asserted_workload_evidence, normalize_monthly_volume,
                       monthly_volume_from_enquiry, monthly_volume_proposal, scenario_volume_from_enquiry)

FIELDS = set(get_args(FactId))


def context_from_result(result, state, enquiry):
    interpretation = result['diagnostic_context']['interpretation']
    qualification = result['outputs'].get('qualification_details', {})
    _merge_monthly_workload(state, qualification, enquiry)
    for field in FIELDS - {'monthly_volume'}:
        value = qualification.get(field)
        if value is not None and not (field in state.facts and state.facts[field].status == 'supplied'):
            state.facts[field] = DiagnosticFact(field=field, value=value, source='interpretation',
                                               evidence=f'qualification_details.{field}')
    previous_stops = state.facts.get('max_stops')
    if previous_stops and previous_stops.status == 'supplied' and (previous_stops.source == 'query' or previous_stops.source.startswith('history[')):
        context = requirement_evidence(enquiry, previous_stops.evidence)
        if not context or not route_count_proposal(previous_stops.value, context[1]):
            state.facts['max_stops'] = previous_stops.model_copy(update={'status': 'missing'})
    for proposal in extract_requirements(enquiry):
        state.facts[proposal['field']] = DiagnosticFact(**proposal)
    for source, text in customer_texts(enquiry):
        patterns = [
            ('details_sku', r'\b(?:ending|ends?|terminated?|terminating)\s+(?:in|with|by)\s+((?:Place Details|Address Validation)[^.\n,;]*)'),
        ]
        for field, pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                value = True if field in {'storage_required', 'traffic_required'} else (match.group(1) if match.lastindex else match.group())
                state.facts[field] = DiagnosticFact(field=field, value=value, source=source,
                                                    evidence=match.group(), start=match.start(), end=match.end())
    for source, text in customer_texts(enquiry):
        for match in re.finditer(r'(?i:\b(?:shown|displayed|instructions|returned)\s+in)\s+([A-Z][A-Za-z-]*(?:,\s*[A-Z][A-Za-z-]*)*(?:\s+and\s+[A-Z][A-Za-z-]*)?)', text):
            state.facts['languages'] = DiagnosticFact(field='languages',value=match.group(1),source=source,evidence=match.group(),start=match.start(),end=match.end())
    for question in state.questions:
        if question.status == 'asked' and all(state.facts.get(f) and state.facts[f].status == 'supplied' for f in question.facts):
            question.status = 'answered'
    return QualificationContext(api=interpretation['api'], intent=interpretation['intent'],
        facts={field:fact for field,fact in state.facts.items() if field in FIELDS},
        assumptions={'monthly_volume': state.facts['monthly_volume_assumption']}
            if 'monthly_volume_assumption' in state.facts else {},
        missing_interpretation_fields=qualification.get('missing_required_fields', []))


def merge_model_facts(state, plan, enquiry):
    sources = customer_texts(enquiry)
    source_order = {source: index for index, (source, _) in enumerate(sources)}
    boolean_fields = {'storage_required','traffic_required','details_completion','debouncing',
        'session_tokens','api_enabled','existing_project','hazmat_required','requests_splittable',
        'redistribution_required','resale_required','address_elements_required','rooftop_hard_filter',
        'public_service_acceptable','temporary_results_acceptable','mapbox_traffic_profile'}
    for proposal in plan.supplied_facts:
        if not proposal.evidence.strip():
            continue
        if proposal.field == 'max_stops':
            context = requirement_evidence(enquiry, proposal.evidence)
            if not context or not route_count_proposal(proposal.value, context[1]) or not route_count_proposal(proposal.value, proposal.evidence):
                continue
        if isinstance(proposal.value, bool) and proposal.field not in boolean_fields:
            continue
        if proposal.field == 'monthly_volume':
            source = next((source for source,text in reversed(customer_texts(enquiry)) if proposal.evidence in text),None)
            text = dict(sources).get(source, '')
            value = monthly_volume_proposal(proposal.value, proposal.evidence) if source and asserted_workload_evidence(text, proposal.evidence) else None
            latest, latest_source = monthly_volume_from_enquiry(enquiry)
            if value and latest and source == latest_source and all(
                value[key] == latest[key] for key in ('requests_per_month', 'unit')
            ):
                state.facts['monthly_volume'] = DiagnosticFact(field='monthly_volume',value=latest,
                    source=latest_source,evidence=latest['raw'])
            continue
        source = next((source for source,text in reversed(sources) if proposal.evidence in text), None)
        if source is None:
            continue
        if proposal.field in {'storage_required','traffic_required','details_completion','debouncing',
            'session_tokens','api_enabled','existing_project','hazmat_required','requests_splittable',
            'redistribution_required','resale_required','address_elements_required','rooftop_hard_filter',
            'public_service_acceptable','temporary_results_acceptable','mapbox_traffic_profile'}:
            evidence = proposal.evidence
            if proposal.field in {'storage_required', 'traffic_required', 'rooftop_hard_filter', 'address_elements_required'}:
                context = requirement_evidence(enquiry, evidence)
                if not context:
                    continue
                evidence = context[1]
            if not _boolean_evidence(proposal.field, proposal.value, evidence) or re.search(r'\b(?:may|might|possibly|optionally)\b', proposal.evidence, re.I):
                continue
        if not isinstance(proposal.value, bool) and not _literal_or_alias(proposal.field, proposal.value, proposal.evidence):
            continue
        previous = state.facts.get(proposal.field)
        if previous and previous.status == 'supplied' and previous.value is not None:
            assertion = requirement_evidence(enquiry, proposal.evidence)
            if not assertion or assertion[0] != source or previous.source == 'interpretation':
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


_BOOL_ANCHORS = {
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


def _literal_or_alias(field, value, evidence):
    normalized = lambda text: re.sub(r'[^a-z0-9]', '', str(text).casefold())
    if normalized(value) in {'unknown','unspecified','notspecified','notprovided','na'}:
        return False
    if normalized(value) and normalized(value) in normalized(evidence):
        return True
    aliases = {
        'instruction_modality': {'voice':r'\bspoken|\baudio|\btts\b', 'text':r'\bwritten\b'},
        'lookup_trigger': {'user-triggered':r'\bmanual|\bon demand|\buser.initiated|\bclick',
                          'periodic':r'\bperiodic|\bscheduled|\bpolling'},
    }
    pattern=aliases.get(field,{}).get(str(value).casefold())
    return bool(pattern and re.search(pattern,evidence,re.I))


def _merge_monthly_workload(state, qualification, enquiry):
    previous=state.facts.get('monthly_volume')
    explicit,source=monthly_volume_from_enquiry(enquiry)
    scenario, scenario_source = scenario_volume_from_enquiry(enquiry)
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
    elif previous or qualification.get('monthly_volume') is not None:
        # Partial quantities stay visible but cannot suppress the workload question.
        state.facts['monthly_volume']=DiagnosticFact(field='monthly_volume',status=previous.status if previous and previous.status in {'asked','declined'} else 'missing',
            value=qualification.get('monthly_volume') if qualification.get('monthly_volume') is not None else previous.value,
            source='qualification_normalization',evidence='Monthly API quantity and workload unit are not both confirmed.')
