# Autocomplete API — Full Reference

## Overview
The Autocomplete API returns address and place suggestions as the user types. It is used for address input fields, search boxes, and location pickers in web and mobile applications.

## Endpoint
GET /v1/autocomplete

## Required Parameters
- q: string — partial address or place name (minimum 2 characters)

## Optional Parameters
- limit: integer — max suggestions to return (default 5, max 10)
- country: ISO 3166-1 alpha-2 code — restrict results to one country (e.g. DE, GB, US)
- language: BCP-47 code — language for result text (default en)
- lat: float — bias results toward this latitude
- lon: float — bias results toward this longitude
- radius_m: integer — bias radius in metres (used with lat/lon, default 50000)
- types: pipe-separated — address|city|postcode|country|poi

## Response Fields
- suggestions[]: array of suggestion objects
  - place_id: string — unique identifier for the place
  - description: string — full formatted address
  - matched_substrings[]: character ranges matching the query
  - types[]: address | city | postcode | country | poi
  - distance_m: integer — distance from bias point (if lat/lon provided)

## Rate Limits
- Standard: 100 requests/second
- Professional: 500 requests/second
- Enterprise: custom

## Pricing
- Standard: $299/month, up to 500K requests/month; $0.003 per request overage
- Professional: $999/month, up to 5M requests/month; $0.002 per request overage
- Enterprise: custom

## Coverage
- 195 countries for address autocomplete
- POI (points of interest) coverage: 85 countries
- Postcode autocomplete: 60 countries
- Rural address coverage varies by country — best in US, UK, DE, FR, AU

## Session Tokens
- Use session_token parameter to group autocomplete + place detail calls into one billable session
- Generate a new UUID per user input session
- Session billing: one session = one request regardless of keystrokes
- Without session token: each keystroke billed as separate request

## Place Details
- After selecting a suggestion, fetch full details: GET /v1/place/{place_id}
- Returns: formatted_address, lat, lon, components, phone, website, opening_hours
- Place details billed separately from autocomplete

## Competitor Comparison — Autocomplete API

### Provider A (Our Service)
- Coverage: 195 countries
- POI coverage: 85 countries
- Session tokens: supported
- Bias by location: supported
- Pricing: $299/mo Standard, $999/mo Professional

### Provider B
- Coverage: 180 countries
- POI coverage: 60 countries
- Session tokens: supported
- Bias by location: supported
- Pricing: $200/mo Starter, $800/mo Business

### Provider C
- Coverage: 150 countries
- POI coverage: 40 countries
- Session tokens: not supported
- Bias by location: supported
- Pricing: $150/mo Starter, $700/mo Business

## Common Issues
- No results for rural addresses — try removing country filter or reducing specificity
- Results in wrong language — set language parameter explicitly
- Too many requests billed — implement session tokens to reduce billing
- Suggestions not biased to user location — confirm lat/lon and radius_m are set
- Minimum query length — q must be at least 2 characters; shorter queries return empty

## Integration Best Practices
- Debounce input: wait 300ms after last keystroke before sending request
- Use session tokens: group autocomplete + place detail into one session
- Cache results: cache suggestions for identical queries within a session
- Bias to user location: pass device GPS coordinates as lat/lon for relevant results
- Handle empty results gracefully: show "No results found" rather than blank dropdown

## Diagnostic Checklist
1. Confirm q parameter is at least 2 characters
2. Check country filter — remove if results are unexpectedly empty
3. Verify API key has Autocomplete API enabled in dashboard
4. For location bias: confirm lat/lon are valid and radius_m is reasonable
5. Check monthly request quota in dashboard
6. Review response matched_substrings to confirm query is matching correctly
