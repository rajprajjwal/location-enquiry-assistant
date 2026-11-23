# Directions API — Full Reference

## Overview
The Directions API returns turn-by-turn navigation routes between an origin and destination. It supports driving, walking, cycling, and truck modes with optional waypoints.

## Endpoint
GET /v1/directions

## Required Parameters
- origin: string — starting point as "lat,lon" or place name
- destination: string — end point as "lat,lon" or place name
- mode: string — one of: driving, walking, cycling, truck

## Optional Parameters
- waypoints: comma-separated list of intermediate "lat,lon" stops (max 23)
- avoid: pipe-separated list — tolls|highways|ferries
- departure_time: ISO8601 timestamp for traffic-aware routing
- alternatives: boolean — return up to 3 alternative routes (default false)
- language: BCP-47 language code for instruction text (default en)
- units: metric or imperial (default metric)
- traffic_model: best_guess | pessimistic | optimistic (requires departure_time)

## Response Fields
- routes[]: array of route objects
  - summary: string — brief route description
  - legs[]: array of leg objects between waypoints
    - distance_m: integer — distance in metres
    - duration_s: integer — estimated travel time in seconds
    - duration_in_traffic_s: integer — traffic-adjusted duration (if departure_time set)
    - steps[]: turn-by-turn instructions
      - instruction: string
      - distance_m: integer
      - maneuver: string — turn_left | turn_right | straight | roundabout | etc.
  - total_distance_m: integer
  - total_duration_s: integer
  - polyline: encoded polyline string (Google Polyline Algorithm)
- status: OK | ZERO_RESULTS | NOT_FOUND | MAX_WAYPOINTS_EXCEEDED | INVALID_REQUEST

## Rate Limits
- Standard plan: 100 requests/second, 500K requests/month
- Professional plan: 500 requests/second, 5M requests/month
- Enterprise plan: custom, up to 10K requests/second

## Pricing
- Standard: included in $299/month up to 500K requests; $0.005 per request overage
- Professional: included in $999/month up to 5M requests; $0.003 per request overage
- Enterprise: custom volume pricing, contact sales

## Truck Routing
- Supports height, weight, width, length constraints
- Parameters: truck_height_cm, truck_weight_kg, truck_width_cm, truck_length_cm
- Avoids low bridges, weight-restricted roads, hazmat restrictions
- Requires Professional or Enterprise plan

## Real-Time Traffic
- Available in 85 countries
- Uses live traffic feed updated every 2 minutes
- Requires departure_time parameter
- Outside covered countries: falls back to historical traffic patterns

## Waypoints
- Maximum 23 waypoints per request on Standard and Professional
- Enterprise supports up to 150 waypoints
- Waypoint optimisation (reordering for shortest path) available on Professional+
- Optimise parameter: waypoints=optimize:true|lat,lon|lat,lon

## Error Codes
- 400: INVALID_REQUEST — missing required parameter or malformed coordinates
- 401: AUTH_FAILED — invalid or expired API key
- 403: QUOTA_EXCEEDED — monthly quota or rate limit hit
- 404: NOT_FOUND — origin or destination not found
- 422: MISSING_PARAMETER — required field absent
- 429: RATE_LIMITED — requests per second exceeded; check Retry-After header
- 500: INTERNAL_ERROR — transient server error; retry with exponential backoff
- 503: SERVICE_UNAVAILABLE — maintenance window

## Integration Example
```
GET /v1/directions?origin=48.8566,2.3522&destination=51.5074,-0.1278&mode=driving&departure_time=2024-01-15T09:00:00Z
Headers: X-API-Key: gs_your_key_here
```

## SDK Support
- Python: from locationsvc import DirectionsClient
- JavaScript: import { DirectionsClient } from '@locationsvc/web'
- iOS: LocationSvcDirections (Swift)
- Android: LocationSvcDirections (Kotlin)

## Competitor Comparison — Directions API

### Provider A (Our Service)
- Max waypoints: 23 (Standard/Pro), 150 (Enterprise)
- Traffic countries: 85
- Truck routing: Professional+ only
- Pricing: $299/mo Standard, $999/mo Professional

### Provider B
- Max waypoints: 25 (all plans)
- Traffic countries: 60
- Truck routing: all plans
- Pricing: $200/mo Starter, $800/mo Business

### Provider C
- Max waypoints: 10 (Starter), 50 (Business)
- Traffic countries: 40
- Truck routing: Enterprise only
- Pricing: $150/mo Starter, $700/mo Business

## Common Issues
- Waypoints exceeding limit returns MAX_WAYPOINTS_EXCEEDED — split into multiple requests
- Traffic data not returned — ensure departure_time is set and mode is driving
- Polyline not rendering — decode using Google Polyline Algorithm Format
- Truck route ignoring constraints — verify truck parameters are in correct units (cm, kg)

## Diagnostic Checklist
1. Verify API key is valid and not expired
2. Check origin and destination coordinates are within valid range
3. Confirm mode parameter is one of: driving, walking, cycling, truck
4. For traffic: confirm departure_time is ISO8601 and in the future
5. For waypoints: confirm count does not exceed plan limit
6. Check monthly quota in dashboard
