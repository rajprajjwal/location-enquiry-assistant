"""Merge validated interpretation and explicitly evidenced customer requirements."""
import re
from typing import get_args
from copilot.diagnostics.facts import DiagnosticFact
from .contract import FactId, QualificationContext
from .workload import normalize_monthly_volume, monthly_volume_from_enquiry, monthly_volume_proposal

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
    for source, text in customer_texts(enquiry):
        patterns = [
            ('details_sku', r'\b(?:ending|ends?|terminated?|terminating)\s+(?:in|with|by)\s+((?:Place Details|Address Validation)[^.\n,;]*)'),
            ('storage_required', r'\b(?:must|need to|will)\s+store\s+(?:the\s+)?(?:addresses|results|responses)\b'),
            ('traffic_required', r'\b(?:under|with|need|needs|want|wants)\s+(?:live[- ]traffic|live traffic|traffic-aware)\b'),
            ('max_stops', r'\b(\d+(?:\s*[–-]\s*\d+)?)\s+(?:outlets|stops|waypoints)\b'),
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
        missing_interpretation_fields=qualification.get('missing_required_fields', []))


def customer_texts(enquiry):
    return [(f'history[{i}]', turn['text']) for i,turn in enumerate(enquiry.get('history', [])) if turn['role']=='user'] + [('query', enquiry['query'])]


def merge_model_facts(state, plan, enquiry):
    boolean_fields = {'storage_required','traffic_required','details_completion','debouncing',
        'session_tokens','api_enabled','existing_project','hazmat_required','requests_splittable',
        'redistribution_required','resale_required','address_elements_required','rooftop_hard_filter',
        'public_service_acceptable','temporary_results_acceptable','mapbox_traffic_profile'}
    for proposal in plan.supplied_facts:
        if isinstance(proposal.value, bool) and proposal.field not in boolean_fields:
            continue
        if proposal.field == 'monthly_volume':
            source = next((source for source,text in reversed(customer_texts(enquiry)) if proposal.evidence in text),None)
            value = monthly_volume_proposal(proposal.value, proposal.evidence) if source else None
            if value:
                state.facts['monthly_volume'] = DiagnosticFact(field='monthly_volume',value=value,source=source,evidence=proposal.evidence)
            continue
        source = next((source for source,text in reversed(customer_texts(enquiry)) if proposal.evidence in text), None)
        if source is None:
            continue
        if proposal.field in {'storage_required','traffic_required','details_completion','debouncing',
            'session_tokens','api_enabled','existing_project','hazmat_required','requests_splittable',
            'redistribution_required','resale_required','address_elements_required','rooftop_hard_filter',
            'public_service_acceptable','temporary_results_acceptable','mapbox_traffic_profile'}:
            if not _boolean_evidence(proposal.field, proposal.value, proposal.evidence) or re.search(r'\b(?:may|might|possibly|optionally)\b', proposal.evidence, re.I):
                continue
        if not isinstance(proposal.value, bool) and not _literal_or_alias(proposal.field, proposal.value, proposal.evidence):
            continue
        previous = state.facts.get(proposal.field)
        # Explicit extraction and validated interpretation take priority over model inference.
        if previous and previous.status == 'supplied' and previous.value is not None:
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
    candidates=[qualification.get('monthly_volume'),previous.value if previous else None]
    normalized=explicit or next((v for value in candidates if (v:=normalize_monthly_volume(value)) is not None),None)
    if normalized:
        state.facts['monthly_volume']=DiagnosticFact(field='monthly_volume',value=normalized,
            source=source if explicit else 'normalized_qualification', evidence=normalized['raw'])
    elif previous or qualification.get('monthly_volume') is not None:
        # Partial quantities stay visible but cannot suppress the workload question.
        state.facts['monthly_volume']=DiagnosticFact(field='monthly_volume',status=previous.status if previous and previous.status in {'asked','declined'} else 'missing',
            value=qualification.get('monthly_volume') if qualification.get('monthly_volume') is not None else previous.value,
            source='qualification_normalization',evidence='Monthly API quantity and workload unit are not both confirmed.')
