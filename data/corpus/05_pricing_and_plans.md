# Pricing, Plans and Limits — Full Reference

## Plan Overview

### Standard Plan — $299/month
- Location API calls: 500K/month
- Directions API: included
- Distance Matrix: 25×25 elements per request, 500K elements/month
- Autocomplete: 500K requests/month
- Reverse Geocode: 500K requests/month
- Geofences: up to 100 active
- Route optimisation: not included
- Indoor positioning: not included
- WebSocket streaming: not included
- Batch geocoding: not included
- Support: email, 48-hour SLA
- Uptime SLA: 99.9%
- Data residency: not available

### Professional Plan — $999/month
- Location API calls: 5M/month
- Directions API: included, up to 150 waypoints
- Distance Matrix: 50×50 elements per request, 5M elements/month
- Autocomplete: 5M requests/month
- Reverse Geocode: 5M requests/month
- Geofences: up to 1000 active
- Route optimisation: included (TSP and VRP)
- Indoor positioning: not included
- WebSocket streaming: included
- Batch geocoding: up to 1000 addresses per request
- Batch reverse geocode: up to 1000 coordinates per request
- Support: chat and email, 8-hour SLA
- Uptime SLA: 99.95%
- Data residency: not available

### Enterprise Plan — Custom Pricing
- Location API calls: unlimited
- Directions API: included, up to 150 waypoints, custom higher limits available
- Distance Matrix: 100×100 per request, async batch up to 1000×1000
- Autocomplete: unlimited
- Reverse Geocode: unlimited, batch up to 1000
- Geofences: unlimited
- Route optimisation: included
- Indoor positioning: included (requires site survey)
- WebSocket streaming: included
- Batch geocoding: included
- Dedicated support engineer: included
- Support SLA: 1-hour response
- Uptime SLA: 99.99%
- Data residency: EU, US, APAC available
- Custom SLA negotiation: available
- IP allowlisting: available
- DPA (Data Processing Agreement): available

## Overage Pricing
- Directions: $0.005/request (Standard), $0.003/request (Professional)
- Distance Matrix: $0.004/element (Standard), $0.002/element (Professional)
- Autocomplete: $0.003/request (Standard), $0.002/request (Professional)
- Reverse Geocode: $0.004/request (Standard), $0.002/request (Professional)

## Volume Discounts (Enterprise)
- 10M–50M requests/month: 20% discount on list price
- 50M–200M requests/month: 35% discount on list price
- 200M+ requests/month: 50% discount on list price
- Annual commitment: additional 10% discount

## Plan Upgrade Triggers
- Upgrade Standard → Professional if:
  - Monthly requests exceed 500K
  - Need WebSocket streaming
  - Need route optimisation
  - Need batch geocoding
  - Need Distance Matrix > 25×25
- Upgrade Professional → Enterprise if:
  - Monthly requests exceed 5M
  - Need indoor positioning
  - Need data residency guarantees
  - Need 99.99% SLA
  - Need Distance Matrix > 50×50
  - Need >10,000 concurrent devices
  - Need custom integration support

## Competitor Plan Comparison

### Standard/Starter Tier
| Feature | Our Standard ($299) | Provider B Starter ($200) | Provider C Starter ($150) |
|---------|--------------------|--------------------------|-----------------------------|
| Monthly requests | 500K | 300K | 200K |
| Matrix limit | 25×25 | 10×10 | 5×5 |
| Geofences | 100 | 50 | 20 |
| WebSocket | No | No | No |
| SLA | 99.9% | 99.5% | 99.0% |

### Professional/Business Tier
| Feature | Our Professional ($999) | Provider B Business ($800) | Provider C Business ($700) |
|---------|------------------------|---------------------------|---------------------------|
| Monthly requests | 5M | 3M | 2M |
| Matrix limit | 50×50 | 25×25 | 25×25 |
| Geofences | 1000 | 500 | 200 |
| WebSocket | Yes | Yes | No |
| Route optimisation | Yes | No | No |
| SLA | 99.95% | 99.9% | 99.5% |
