# Reverse Geocode API — Full Reference

## Overview
The Reverse Geocode API converts GPS coordinates (latitude, longitude) into a human-readable address. It is used in fleet tracking, delivery confirmation, incident reporting, and location tagging.

## Endpoint
GET /v1/reverse

## Required Parameters
- lat: float — latitude in WGS84 decimal degrees (-90 to 90)
- lon: float — longitude in WGS84 decimal degrees (-180 to 180)

## Optional Parameters
- language: BCP-47 code — language for address text (default en)
- result_types: pipe-separated — street_address|route|locality|postal_code|country|administrative_area
- location_type: ROOFTOP|RANGE_INTERPOLATED|GEOMETRIC_CENTER|APPROXIMATE

## Response Fields
- results[]: array of address objects (most specific first)
  - formatted_address: string — full human-readable address
  - address_components[]: structured components
    - long_name: string
    - short_name: string
    - types[]: street_number|route|locality|postal_code|country|etc.
  - geometry:
    - location: { lat, lon }
    - location_type: ROOFTOP | RANGE_INTERPOLATED | GEOMETRIC_CENTER | APPROXIMATE
  - place_id: string
  - types[]: address type tags
- status: OK | ZERO_RESULTS | INVALID_REQUEST | REQUEST_DENIED

## Rate Limits
- Standard: 100 requests/second
- Professional: 500 requests/second
- Enterprise: custom

## Pricing
- Standard: $299/month, up to 500K requests/month; $0.004 per request overage
- Professional: $999/month, up to 5M requests/month; $0.002 per request overage
- Enterprise: custom

## Coverage
- 195 countries
- Street-level (ROOFTOP) accuracy: 120 countries
- Road-level (RANGE_INTERPOLATED) accuracy: 195 countries
- Rural areas may return GEOMETRIC_CENTER or APPROXIMATE results

## Batch Reverse Geocoding
- Endpoint: POST /v1/reverse/batch
- Accepts up to 1000 coordinate pairs per request
- Available on Professional and Enterprise plans only
- Response: array of result objects in same order as input

## Coordinate Precision
- 6 decimal places recommended (±0.11m precision)
- 4 decimal places acceptable (±11m precision)
- Fewer than 4 decimal places may return incorrect street-level results

## Competitor Comparison — Reverse Geocode API

### Provider A (Our Service)
- Coverage: 195 countries
- Street-level accuracy: 120 countries
- Batch: up to 1000 (Professional+)
- Pricing: $299/mo Standard, $999/mo Professional

### Provider B
- Coverage: 180 countries
- Street-level accuracy: 90 countries
- Batch: not supported
- Pricing: $200/mo Starter, $800/mo Business

### Provider C
- Coverage: 160 countries
- Street-level accuracy: 80 countries
- Batch: up to 500 (Enterprise only)
- Pricing: $150/mo Starter, $700/mo Business

## Common Issues
- ZERO_RESULTS — coordinates are in ocean, uninhabited area, or outside coverage
- APPROXIMATE result — coordinates are in rural area without street-level data
- Wrong country returned — verify coordinate order is lat then lon (not lon, lat)
- Non-English addresses — set language parameter to desired BCP-47 code
- Batch not available — upgrade to Professional or Enterprise plan

## Use Cases
- Fleet tracking: convert vehicle GPS position to readable address for dispatcher
- Delivery confirmation: record delivery address from driver GPS at time of delivery
- Incident reporting: tag incident location with address for support ticket
- Geofence alerts: include human-readable address in geofence enter/exit notifications
- Customer apps: show user their current address without requiring them to type it

## Diagnostic Checklist
1. Confirm lat is between -90 and 90, lon is between -180 and 180
2. Verify coordinate order — lat must come before lon
3. Use at least 4 decimal places for street-level accuracy
4. Check result location_type — APPROXIMATE means limited street data in that area
5. For batch: confirm plan is Professional or Enterprise
6. Check monthly quota in dashboard
