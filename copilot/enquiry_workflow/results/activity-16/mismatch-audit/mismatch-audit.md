# Activity 16 ownership mismatch audit

This audit covers the 26 mismatches from the saved frozen run. The frozen data and predictions are preserved. No frozen cases were scored with the revised router.

## Working-eval validation

Routine ownership was replayed using saved interpretations and the corrected working labels. Development improved from 134/147 (91.16%) to 135/147 (91.84%). The separate 12-case validation sample remained 8/12 (66.67%). Recorded model handoff decisions were reused. This check measures the changed routine rules independently of model variability. All 85 workflow tests passed with the real interpretation validator, including handoff and approval tests.

## Ownership decisions requiring review

### Public estimates

Support L1 under the approved public-pricing policy. Review the frozen owner label.

Cases: AC-236, DIR-020, DIR-021, DM-026, DM-027, DM-233.

### Provider fit and coverage

Decide whether first ownership for documented capability or coverage comparisons belongs to Sales or Support L1. Working labels assign DM-093 coverage to Support L1 and AC-212 launch coverage to Sales.

Cases: AC-205, AC-230, DIR-039, DIR-113, DIR-216, DM-201, DM-221, DM-222, RG-201, RG-234.

### Provider cost comparison

Sales follows the approved provider-selection rule. Review these Support L1 frozen labels against that rule.

Cases: DM-117, DM-118.

### Licensing and usage policy

Decide whether public licensing and usage questions remain in Support L1, with Sales owning contractual exceptions. RG-082 is a public usage-policy question despite its interpreted sales intent.

Cases: DIR-043, RG-082, RG-226.

### Technical qualification

Decide whether technical API-selection clarification for a prospect belongs to Sales or Support L1. Working DM-228 assigns qualification before a provider recommendation to Sales.

Cases: DM-094.

### Billing handoff

Choose Sales for billing-policy confirmation, or Support L2 as the initial human reviewer. Existing billing_incident category requires a service-stopping incident, which this case does not establish.

Cases: AC-234.

### Address-quality triage

Choose Support L2 to investigate a reported interpolation/precision issue before proving a map-data defect, or Maps engineering for direct data-quality handoff.

Cases: RG-232.

## Complete case audit

| Case | Query and earlier request | Gold owner | Predicted owner | Assessment |
|---|---|---|---|---|
| GT-LBS-AC-205 | Our users type addresses in Hindi. Which autocomplete providers can return Hindi suggestions? | Account team (Sales) | Support L1 | Decide whether first ownership for documented capability or coverage comparisons belongs to Sales or Support L1. Working labels assign DM-093 coverage to Support L1 and AC-212 launch coverage to Sales. |
| GT-LBS-AC-230 | We need type-ahead place suggestions that we can bias to a search area and filter by place type. Which of Google Places Autocomplete (New), Ola Places Autocomplete, and Mapbox Search Box document those capabilities? | Account team (Sales) | Support L1 | Decide whether first ownership for documented capability or coverage comparisons belongs to Sales or Support L1. Working labels assign DM-093 coverage to Support L1 and AC-212 launch coverage to Sales. |
| GT-LBS-AC-234 | We are a standard self-service Ola Maps customer using Autocomplete with automatic card billing. Official pricing is changing in September 2026. Please prepare a handoff for a human billing reviewer to confirm what we need to do about prepaid credits for Autocomplete. | Account team (Sales) | Support L2 | Choose Sales for billing-policy confirmation, or Support L2 as the initial human reviewer. Existing billing_incident category requires a service-stopping incident, which this case does not establish. |
| GT-LBS-AC-236 | New Places API SKU, please. Just show USD. Earlier request: We expect 40,000 Google Places Autocomplete Requests per month on the global price card. What is the free allowance and estimated charge? | Account team (Sales) | Support L1 | Support L1 under the approved public-pricing policy. Review the frozen owner label. |
| GT-LBS-DIR-020 | Not sure. Answer with the details from my first message and note where that choice would change things. Earlier request: Quote Google Maps Platform routing for 500,000 requests a month in India. Routes have 4 stops, no traffic needed. | Account team (Sales) | Support L1 | Support L1 under the approved public-pricing policy. Review the frozen owner label. |
| GT-LBS-DIR-021 | Let's leave that open for now; answer based on my earlier message. Earlier request: Quote Google Maps Platform routing for 2,000,000 requests a month in India. Routes have 6 stops and we need traffic-aware ETAs. | Account team (Sales) | Support L1 | Support L1 under the approved public-pricing policy. Review the frozen owner label. |
| GT-LBS-DIR-039 | Which Directions APIs can return a driving route that avoids ferries, and how can we tell whether that capability is documented? | Account team (Sales) | Support L1 | Decide whether first ownership for documented capability or coverage comparisons belongs to Sales or Support L1. Working labels assign DM-093 coverage to Support L1 and AC-212 launch coverage to Sales. |
| GT-LBS-DIR-043 | If we self-host OSRM on OpenStreetMap data for routing, what licensing obligations do we have? | Account team (Sales) | Support L1 | Decide whether public licensing and usage questions remain in Support L1, with Sales owning contractual exceptions. RG-082 is a public usage-policy question despite its interpreted sales intent. |
| GT-LBS-DIR-113 | Which Directions APIs can return a multi-stop driving route with separate distances and travel times for every leg, while visiting the stops in the order we supply? | Account team (Sales) | Support L1 | Decide whether first ownership for documented capability or coverage comparisons belongs to Sales or Support L1. Working labels assign DM-093 coverage to Support L1 and AC-212 launch coverage to Sales. |
| GT-LBS-DIR-216 | Our drivers prefer Tamil. Can the directions API return turn-by-turn instructions in Tamil? | Account team (Sales) | Support L1 | Decide whether first ownership for documented capability or coverage comparisons belongs to Sales or Support L1. Working labels assign DM-093 coverage to Support L1 and AC-212 launch coverage to Sales. |
| GT-LBS-DM-026 | Google Maps Platform quote: 20,000 matrix requests per month in India, each a 25×4 traffic-aware matrix, on an existing project. | Account team (Sales) | Support L1 | Support L1 under the approved public-pricing policy. Review the frozen owner label. |
| GT-LBS-DM-027 | Google Maps Platform quote: 3,000 matrix requests per month in India, each a 20×20 matrix, on a brand-new GCP project. | Account team (Sales) | Support L1 | Support L1 under the approved public-pricing policy. Review the frozen owner label. |
| GT-LBS-DM-094 | For a ride-hailing ETA screen, a prospect wants to compare travel times from many drivers to one pickup. What should we clarify before recommending an Ola Distance Matrix solution, and when would single-route Directions be useful? | Support L1 | Account team (Sales) | Decide whether technical API-selection clarification for a prospect belongs to Sales or Support L1. Working DM-228 assigns qualification before a provider recommendation to Sales. |
| GT-LBS-DM-117 | Mapbox vs Google matrix cost for 400,000 elements a month, no traffic? | Support L1 | Account team (Sales) | Sales follows the approved provider-selection rule. Review these Support L1 frozen labels against that rule. |
| GT-LBS-DM-118 | Mapbox vs Google matrix cost for 1,000,000 elements a month, no traffic? | Support L1 | Account team (Sales) | Sales follows the approved provider-selection rule. Review these Support L1 frozen labels against that rule. |
| GT-LBS-DM-201 | We're a logistics firm in Lucknow adding Kathmandu. Which distance-matrix providers can cover Nepal as well as India? | Account team (Sales) | Support L1 | Decide whether first ownership for documented capability or coverage comparisons belongs to Sales or Support L1. Working labels assign DM-093 coverage to Support L1 and AC-212 launch coverage to Sales. |
| GT-LBS-DM-214 | We need a 30×30 matrix (900 elements) per request. Which providers accept that in one call? | Support L1 | Account team (Sales) | Capacity per API call belongs to Support L1. Added a general rule and regression tests. |
| GT-LBS-DM-221 | For a grocery dispatcher, what's the practical difference between Ola Distance Matrix and Distance Matrix Basic? | Account team (Sales) | Support L1 | Decide whether first ownership for documented capability or coverage comparisons belongs to Sales or Support L1. Working labels assign DM-093 coverage to Support L1 and AC-212 launch coverage to Sales. |
| GT-LBS-DM-222 | For a field-service scheduler, what's the practical difference between Ola Distance Matrix and Distance Matrix Basic? | Account team (Sales) | Support L1 | Decide whether first ownership for documented capability or coverage comparisons belongs to Sales or Support L1. Working labels assign DM-093 coverage to Support L1 and AC-212 launch coverage to Sales. |
| GT-LBS-DM-226 | A prospect is evaluating Google Distance Matrix for an India-only app. What should we confirm about their intended use and licensing before recommending it, including which published price list would apply? | Account team (Sales) | Support L1 | Qualification before provider recommendation belongs to Sales. Added an explicit qualification rule ahead of public pricing. |
| GT-LBS-DM-233 | Legacy Distance Matrix API. Please use list prices and show USD. Earlier request: Estimate Google Maps Platform India legacy Distance Matrix charges for 100,000 elements per month. Our monthly batch has 10 origins and 10,000 destinations, for 100,000 origin-destination elements in total. What is the free allowance and estimated charge? | Account team (Sales) | Support L1 | Support L1 under the approved public-pricing policy. Review the frozen owner label. |
| GT-LBS-RG-082 | Sandbox CRM ticket TKT-38973. Customer wrote: "Our mobile app calls Nominatim reverse every 30 seconds per user. OK?" Draft the reply and propose the ticket field updates. Don't apply anything until I approve. | Support L1 | Account team (Sales) | Decide whether public licensing and usage questions remain in Support L1, with Sales owning contractual exceptions. RG-082 is a public usage-policy question despite its interpreted sales intent. |
| GT-LBS-RG-201 | We need reverse geocoding for riders in India and Nepal. Who covers both? | Account team (Sales) | Support L1 | Decide whether first ownership for documented capability or coverage comparisons belongs to Sales or Support L1. Working labels assign DM-093 coverage to Support L1 and AC-212 launch coverage to Sales. |
| GT-LBS-RG-226 | Can we store Mapbox reverse-geocoding results in our own database for later reuse, and does the public Nominatim policy allow us to resell those geocoding results? | Account team (Sales) | Support L1 | Decide whether public licensing and usage questions remain in Support L1, with Sales owning contractual exceptions. RG-082 is a public usage-policy question despite its interpreted sales intent. |
| GT-LBS-RG-232 | Customers report that Google reverse geocoding returns a road-interpolated address that does not match the building they selected. Please prepare a handoff to a human to review these quality reports. What should we check and include in the handoff? | Support L2 | Maps engineering | Choose Support L2 to investigate a reported interpolation/precision issue before proving a map-data defect, or Maps engineering for direct data-quality handoff. |
| GT-LBS-RG-234 | Which reverse geocoders document a way to look up many coordinates in a single batch request? | Account team (Sales) | Support L1 | Decide whether first ownership for documented capability or coverage comparisons belongs to Sales or Support L1. Working labels assign DM-093 coverage to Support L1 and AC-212 launch coverage to Sales. |
