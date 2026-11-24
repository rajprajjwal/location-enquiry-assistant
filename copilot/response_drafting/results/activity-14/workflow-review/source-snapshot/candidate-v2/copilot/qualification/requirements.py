"""Describe applicable customer decisions from API, task and explicit requirements."""
import re
from copilot.enquiry_workflow.routing import asks_qualification, discovers_providers, broad_provider_search
from .task import effective_customer_task


def applicable_groups(context, enquiry, pricing):
    text=effective_customer_task(enquiry).casefold()
    asks_checklist=asks_qualification(text)
    recommends=asks_checklist or bool(re.search(r'\brecommend|which.{0,25}(?:best|choose)',text))
    quote=context.intent in {'pricing_quote','pricing_comparison'} or bool(re.search(r'\bcost|\bquote|\bcheaper|\bpricing',text))
    selection=discovers_providers(text) or broad_provider_search(text)
    concrete_workload=bool(context.facts.get('monthly_volume') or context.assumptions.get('monthly_volume')
                           or re.search(r'\d[^.!?\n]{0,100}\b(?:requests?|routes?|sessions?|lookups?)\b[^.!?\n]{0,30}\bmonth', text))
    groups=[]
    def add(fields, impact, *, required=False):
        groups.append({'fields':fields,'decision_impact':impact,'required':required})
    if context.api=='autocomplete':
        if asks_checklist:
            add(['peak_rate','region'],'Check service scale and geographic fit.')
            add(['backend_owner','storage_required','redistribution_required','resale_required'],'Determine backend operating responsibility and required data rights.')
        elif 'nominatim' in text and re.search(r'type.?ahead|autocomplete',text):
            add(['hosting_preference'],'Select a viable backend when the public service cannot support the proposed typeahead use.')
        elif quote and (concrete_workload or re.search(r'\b(?:cost|quote|estimate|pay|bill\w*)\b|how much',text)) and re.search(r'session|keystroke|autocomplete',text):
            if re.search(r'ending|ends? in|terminat',text):
                add(['details_sku'],'Select the applicable session-termination billing rule.')
            else:
                add(['details_completion'],'Determine how autocomplete sessions end for billing.')
                add(['debouncing'],'Convert user keystrokes into the number of billable API requests.')
        elif (re.search(r'\b(?:restrict\w*|radius|inside|within)\b',text)
              and re.search(r'\b(?:countr\w*|radius|km|kilomet\w*|circle|results?)\b',text)):
            # Documentation may answer configuration questions without more customer facts.
            config_instructions = bool(re.search(r'\bhow\s+(?:(?:do|can|should)\s+(?:we|i)\s+|to\s+)',text))
            add(['geographic_matching'],'Distinguish exclusion of out-of-area results from geographic ranking preferences.',
                required=not config_instructions)
        elif selection and re.search(r'\b(?:countr\w*|india|region|focused|coverage)\b',text):
            add(['poi_required'],'Compare coverage for the required result types.', required=True)
    elif context.api=='directions':
        if quote and selection and concrete_workload:
            add(['traffic_required'],'Select traffic-aware versus static routing prices.', required=True)
            add(['travel_mode'],'Compare equivalent vehicle modes across providers.', required=True)
            add(['existing_project'],'Check Google product eligibility for the quoted workload.', required=True)
        elif recommends:
            add(['monthly_volume'],'Estimate the recurring workload and cost.')
            add(['traffic_required'],'Select traffic-aware versus static routing capability.')
            add(['travel_mode'],'Determine vehicle-specific routing support.')
            add(['max_stops'],'Check route shape against waypoint limits.')
            if not re.search(r'self.host|on.prem|\bOSRM\b',text,re.I):
                add(['existing_project','ola_contract'],'Establish product eligibility and applicable commercial terms.')
        elif re.search(r'truck|hazmat|tonne|height|weight',text):
            add(['hazmat_required','vehicle_dimensions'],'Determine the vehicle restrictions that the routing product must enforce.', required=True)
        elif re.search(r'instructions?|turn.by.turn',text) and re.search(r'language|hindi|tamil|kannada|voice|text',text):
            add(['instruction_modality'],'Distinguish text directions from voice navigation requirements.', required=True)
        elif re.search(r'traffic.aware|live.traffic|traffic-aware',text) and re.search(r'which|what.{0,20}set',text):
            add(['departure_time_mode'],'Determine current versus future-departure traffic requirements.', required=True)
        elif re.search(r'\btraffic.aware\b',text) and selection:
            add(['traffic_conditions'],'Distinguish live traffic from historical or typical ETA requirements.', required=True)
        elif re.search(r'\b(?:limits?|quotas?)\b',text) and re.search(r'\b(?:per minute|per second|rps|at peak)\b',text):
            add(['credential_distribution'],'Apply provider rate-limit scopes to the actual traffic distribution.', required=True)
    elif context.api=='distance_matrix':
        if asks_checklist:
            if re.search(r'\b(?:volume|workload|frequency|concurren\w*|matrix[- ]size)\b', text):
                add(['typical_origin_count','maximum_origin_count','typical_destination_count','maximum_destination_count'],
                    'Check typical and largest matrix shapes against product request limits.')
                add(['matrices_per_hour','matrices_per_month','peak_concurrency'],
                    'Compare recurring usage and simultaneous request load on equivalent units.')
                add(['traffic_conditions','departure_time_mode','requests_splittable'],
                    'Select suitable traffic estimates and determine whether large requests can be divided.')
            else:
                add(['origin_count','destination_count','traffic_required'],'Select a service and request shape that supports the required matrix and ETA capability.')
                if 'mapbox' in text:
                    add(['mapbox_traffic_profile'],'Check the coordinate cap if the Mapbox traffic profile is required.')
        elif quote:
            if 'ola' in text and not re.search(r'\bvs\b|versus|compare|with and without',text):
                add(['traffic_required','travel_mode'],'Check the required matrix features before applying the documented price and limits.')
            elif 'google' in text and not re.search(r'with and without|\bvs\b|versus',text):
                add(['input_type'],'Choose the correct request representation and applicable processing constraints.')
    elif context.api=='reverse_geocode':
        if asks_checklist and re.search(r'rooftop|precision|address.{0,15}elements',text):
            add(['rooftop_hard_filter','address_elements_required'],'Determine the required filtering behavior and response structure.')
            add(['alternative_providers'],'Establish which additional providers should be evaluated.')
        elif asks_checklist:
            add(['peak_rate','monthly_volume'],'Check throughput and recurring usage before recommending a service.')
            add(['languages'],'Establish the required output-language support.')
            add(['storage_required','public_service_acceptable','temporary_results_acceptable'],'Select a deployment and licensing model compatible with the customer use.')
        elif quote:
            add(['storage_required'],'Select temporary versus retained-result licensing and prices.')
            if re.search(r'options|each provider|nominatim',text):
                add(['lookup_trigger'],'Check public-service usage-policy compatibility for interactive versus periodic use.')
    if pricing.get('applicable'):
        add(pricing.get('required_facts') or ['billing_country','usage_geography'],'Qualify the applicable regional price schedule.', required=True)
    return groups
