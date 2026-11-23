# Distance Matrix API — Full Reference

## Overview
The Distance Matrix API computes travel times and distances between multiple origins and destinations in a single request. It is used for logistics optimisation, delivery routing, and service area analysis.

## Endpoint
POST /v1/matrix

## Required Parameters
- origins: array of "lat,lon" strings or place names
- destinations: array of "lat,lon" strings or place names
- mode: string — one of: driving, walking, cycling, truck

## Optional Parameters
- departure_time: ISO8601 timestamp for traffic-aware durations
- avoid: pipe-separated — tolls|highways|ferries
- units: metric or imperial
- traffic_model: best_guess | pessimistic | optimistic

## Matrix Size Limits
- Standard plan: max 25 origins × 25 destinations = 625 elements per request
- Professional plan: max 50 origins × 50 destinations = 2500 elements per request
- Enterprise plan: max 100 origins × 100 destinations = 10000 elements per request
- For larger matrices: use async batch endpoint POST /v1/matrix/batch

## Async Batch Endpoint
- POST /v1/matrix/batch — submit large matrix job
- Returns job_id immediately
- Poll GET /v1/matrix/batch/{job_id} for status: pending | processing | complete | failed
- Results available for 24 hours after completion
- Max batch size: 1000 origins × 1000 destinations (Enterprise only)

## Response Fields
- rows[]: array indexed by origin
  - elements[]: array indexed by destination
    - status: OK | NOT_FOUND | ZERO_RESULTS
    - distance: { value_m: integer, text: string }
    - duration: { value_s: integer, text: string }
    - duration_in_traffic: { value_s: integer, text: string } (if departure_time set)
- origin_addresses[]: resolved address strings
- destination_addresses[]: resolved address strings

## Rate Limits
- Standard: 10 requests/second
- Professional: 50 requests/second
- Enterprise: custom

## Pricing
- Standard: $299/month, up to 500K elements/month; $0.004 per element overage
- Professional: $999/month, up to 5M elements/month; $0.002 per element overage
- Enterprise: custom pricing per element

## Calculating Batches for Large Jobs
- Example: 500 origins × 500 destinations = 250,000 elements
- On Professional (50×50 limit): ceil(500/50) × ceil(500/50) = 10 × 10 = 100 requests
- On Enterprise (100×100 limit): ceil(500/100) × ceil(500/100) = 5 × 5 = 25 requests
- Use async batch endpoint for jobs over plan element limit

## Competitor Comparison — Distance Matrix API

### Provider A (Our Service)
- Standard limit: 25×25 = 625 elements
- Professional limit: 50×50 = 2500 elements
- Enterprise limit: 100×100 = 10000 elements
- Async batch: up to 1000×1000 (Enterprise)
- Pricing: $299/mo Standard, $999/mo Professional

### Provider B
- All plans: 10×10 = 100 elements per request
- No async batch endpoint
- Pricing: $200/mo Starter, $800/mo Business

### Provider C
- Starter: 5×5 = 25 elements
- Business: 25×25 = 625 elements
- Enterprise: 50×50 = 2500 elements
- Async batch: up to 500×500 (Enterprise)
- Pricing: $150/mo Starter, $700/mo Business

## Common Issues
- 400 MATRIX_TOO_LARGE — reduce origins or destinations to fit plan limit
- Elements returning NOT_FOUND — verify coordinates are valid and geocodable
- Traffic durations not returned — set departure_time and use driving mode
- Async job stuck in processing — check status after 5 minutes; contact support if >30 min

## Use Cases
- Last-mile delivery: compute delivery times from depot to all customer addresses
- Service area analysis: find all customers within 30-minute drive
- Driver assignment: match nearest available driver to each order
- Facility location: find optimal warehouse location minimising total travel time

## Diagnostic Checklist
1. Count origins × destinations — confirm within plan limit
2. For large jobs: use async batch endpoint
3. Verify all coordinates are valid lat/lon pairs
4. For traffic: set departure_time in ISO8601 format
5. Check element-level status field — NOT_FOUND means coordinate not routable
6. Monitor monthly element quota in dashboard
