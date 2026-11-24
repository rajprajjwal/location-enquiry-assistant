# Activity 16 customer ownership policy

Existing customers receive routine pricing and technical guidance from Support. New customers receive Sales qualification. Billing-policy handoffs go to Sales. Reported address-quality issues start with Support L2 human triage. Explicit custom contract or pricing requirements continue through commercial routing.

Customer status requires explicit wording. Provider names and workload numbers alone do not establish an existing account. Where no status evidence exists, the existing enquiry-specific routing rules remain the fallback.

## Working-eval validation

Routine routing was replayed with saved interpretations. Recorded model handoffs were retained. The development sample scored 135/147 (91.84%). The separate 12-case sample scored 8/12 (66.67%). All 102 workflow tests passed with the real interpretation validator. The tests include customer status, billing-policy handoffs, and Support L2 address-quality triage.

## Customer status needing confirmation

The following saved frozen mismatches have no explicit new/existing status. Confirm status from customer records before changing gold ownership. The status review below does not change frozen labels or score a revised router on frozen cases.

| Case | Customer query |
|---|---|
| GT-LBS-AC-205 | Our users type addresses in Hindi. Which autocomplete providers can return Hindi suggestions? |
| GT-LBS-AC-230 | We need type-ahead place suggestions that we can bias to a search area and filter by place type. Which of Google Places Autocomplete (New), Ola Places Autocomplete, and Mapbox Search Box document those capabilities? |
| GT-LBS-AC-236 | New Places API SKU, please. Just show USD. Earlier request: We expect 40,000 Google Places Autocomplete Requests per month on the global price card. What is the free allowance and estimated charge? |
| GT-LBS-DIR-020 | Not sure. Answer with the details from my first message and note where that choice would change things. Earlier request: Quote Google Maps Platform routing for 500,000 requests a month in India. Routes have 4 stops, no traffic needed. |
| GT-LBS-DIR-021 | Let's leave that open for now; answer based on my earlier message. Earlier request: Quote Google Maps Platform routing for 2,000,000 requests a month in India. Routes have 6 stops and we need traffic-aware ETAs. |
| GT-LBS-DIR-039 | Which Directions APIs can return a driving route that avoids ferries, and how can we tell whether that capability is documented? |
| GT-LBS-DIR-043 | If we self-host OSRM on OpenStreetMap data for routing, what licensing obligations do we have? |
| GT-LBS-DIR-113 | Which Directions APIs can return a multi-stop driving route with separate distances and travel times for every leg, while visiting the stops in the order we supply? |
| GT-LBS-DIR-216 | Our drivers prefer Tamil. Can the directions API return turn-by-turn instructions in Tamil? |
| GT-LBS-DM-027 | Google Maps Platform quote: 3,000 matrix requests per month in India, each a 20×20 matrix, on a brand-new GCP project. |
| GT-LBS-DM-117 | Mapbox vs Google matrix cost for 400,000 elements a month, no traffic? |
| GT-LBS-DM-118 | Mapbox vs Google matrix cost for 1,000,000 elements a month, no traffic? |
| GT-LBS-DM-201 | We're a logistics firm in Lucknow adding Kathmandu. Which distance-matrix providers can cover Nepal as well as India? |
| GT-LBS-DM-214 | We need a 30×30 matrix (900 elements) per request. Which providers accept that in one call? |
| GT-LBS-DM-221 | For a grocery dispatcher, what's the practical difference between Ola Distance Matrix and Distance Matrix Basic? |
| GT-LBS-DM-222 | For a field-service scheduler, what's the practical difference between Ola Distance Matrix and Distance Matrix Basic? |
| GT-LBS-DM-233 | Legacy Distance Matrix API. Please use list prices and show USD. Earlier request: Estimate Google Maps Platform India legacy Distance Matrix charges for 100,000 elements per month. Our monthly batch has 10 origins and 10,000 destinations, for 100,000 origin-destination elements in total. What is the free allowance and estimated charge? |
| GT-LBS-RG-082 | Sandbox CRM ticket TKT-38973. Customer wrote: "Our mobile app calls Nominatim reverse every 30 seconds per user. OK?" Draft the reply and propose the ticket field updates. Don't apply anything until I approve. |
| GT-LBS-RG-201 | We need reverse geocoding for riders in India and Nepal. Who covers both? |
| GT-LBS-RG-226 | Can we store Mapbox reverse-geocoding results in our own database for later reuse, and does the public Nominatim policy allow us to resell those geocoding results? |
| GT-LBS-RG-234 | Which reverse geocoders document a way to look up many coordinates in a single batch request? |
