"""Describe applicable customer decisions from API, task and explicit requirements."""
import re


def applicable_groups(context, enquiry, pricing):
    text=enquiry['query'].casefold()
    asks_checklist=bool(re.search(r'what (?:should|do|must) (?:we|i) ask|what should we ask|before recommend',text))
    recommends=asks_checklist or bool(re.search(r'\brecommend|which.{0,25}(?:best|choose)',text))
    quote=context.intent in {'pricing_quote','pricing_comparison'} or bool(re.search(r'\bcost|\bquote|\bcheaper|\bpricing',text))
    groups=[]
    def add(fields, impact): groups.append({'fields':fields,'decision_impact':impact})
    if context.api=='autocomplete':
        if asks_checklist:
            add(['peak_rate','region'],'Check service scale and geographic fit.')
            add(['backend_owner','storage_required','redistribution_required','resale_required'],'Determine backend operating responsibility and required data rights.')
        elif 'nominatim' in text and re.search(r'type.?ahead|autocomplete',text):
            add(['hosting_preference'],'Select a viable backend when the public service cannot support the proposed typeahead use.')
        elif quote and re.search(r'session|keystroke|autocomplete',text):
            if re.search(r'ending|ends? in|terminat',text):
                add(['details_sku'],'Select the applicable session-termination billing rule.')
            else:
                add(['details_completion'],'Determine how autocomplete sessions end for billing.')
                add(['debouncing'],'Convert user keystrokes into the number of billable API requests.')
    elif context.api=='directions':
        if recommends:
            add(['monthly_volume'],'Estimate the recurring workload and cost.')
            add(['traffic_required'],'Select traffic-aware versus static routing capability.')
            add(['travel_mode'],'Determine vehicle-specific routing support.')
            add(['max_stops'],'Check route shape against waypoint limits.')
            add(['existing_project','commercial_plan'],'Establish product eligibility and applicable commercial terms.')
        elif re.search(r'truck|hazmat|tonne|height|weight',text):
            add(['hazmat_required','vehicle_dimensions'],'Determine the vehicle restrictions that the routing product must enforce.')
        elif re.search(r'instructions?|turn.by.turn',text) and re.search(r'language|hindi|tamil|kannada|voice|text',text):
            add(['instruction_modality'],'Distinguish text directions from voice navigation requirements.')
        elif re.search(r'traffic.aware|live.traffic|traffic-aware',text) and re.search(r'which|what.{0,20}set',text):
            add(['departure_time_mode'],'Determine current versus future-departure traffic requirements.')
    elif context.api=='distance_matrix':
        if asks_checklist:
            add(['origin_count','destination_count','traffic_required'],'Select a service and request shape that supports the required matrix and ETA capability.')
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
        add(pricing.get('required_facts') or ['billing_country','usage_geography'],'Qualify the applicable regional price schedule.')
    return groups
