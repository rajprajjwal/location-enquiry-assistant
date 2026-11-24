"""Render one staff question for each selected customer decision."""
PHRASES = {
    'region':'target countries or regions', 'monthly_volume':'expected monthly API workload',
    'peak_rate':'peak requests per second', 'timeline':'target launch date', 'sla':'required SLA',
    'budget':'budget', 'current_provider':'current provider', 'alternative_providers':'other providers you want to consider',
    'backend_owner':'who will operate the API backend', 'deployment_owner':'who will own deployment',
    'hosting_preference':'whether self-hosting is acceptable or a managed API is required',
    'billing_country':'billing account country', 'usage_geography':'where most requests will be used',
    'billing_basis':'which API product and billing option you intend to use',
    'billing_account_scope':'whether usage covers one billing account or multiple accounts',
    'commercial_plan':'whether you have a provider contract or prepaid plan',
    'existing_project':'whether you already have an enabled Google project', 'api_enabled':'whether the required API is enabled',
    'details_completion':'whether you call Place Details after a selection',
    'details_sku':'which Place Details SKU terminates the sessions', 'debouncing':'whether you debounce keystrokes',
    'session_tokens':'whether you use a distinct session token for each session',
    'traffic_required':'whether live-traffic ETAs are required', 'traffic_scope':'whether traffic is needed for every matrix or only some',
    'departure_time_mode':'whether traffic is needed now or for future departures', 'travel_mode':'required vehicle or travel modes',
    'max_stops':'maximum stops or waypoints per route', 'hazmat_required':'whether hazardous-goods restrictions are required',
    'vehicle_dimensions':'required height and weight restrictions', 'instruction_modality':'whether instructions must be voice or text',
    'origin_count':'number of origins per matrix', 'destination_count':'number of destinations per matrix',
    'input_type':'whether inputs are coordinates, addresses or place IDs', 'matrix_frequency':'matrices per hour and month',
    'peak_concurrency':'peak concurrent requests', 'mapbox_traffic_profile':'whether Mapbox driving-traffic is required',
    'requests_splittable':'whether requests can be split', 'storage_required':'whether results must be stored',
    'retention_period':'how long results must be retained', 'redistribution_required':'whether results will be redistributed',
    'resale_required':'whether results will be resold', 'display_context':'which map, if any, will display the results',
    'lookup_trigger':'whether lookups are user-triggered or periodic tracking', 'languages':'required output languages',
    'public_service_acceptable':'whether a public community endpoint is acceptable',
    'temporary_results_acceptable':'whether temporary-only geocoding results are acceptable',
    'rooftop_hard_filter':'whether rooftop precision must be a hard filter',
    'address_elements_required':'whether a structured breakdown of address elements is required',
}


def render(fields):
    phrases = [PHRASES[field] for field in fields]
    return 'Could you confirm ' + (', '.join(phrases[:-1]) + ' and ' + phrases[-1] if len(phrases)>1 else phrases[0]) + '?'
