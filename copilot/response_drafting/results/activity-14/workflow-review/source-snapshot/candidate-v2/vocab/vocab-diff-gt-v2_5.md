# Vocabulary diff against GT v2.5

Source of truth: `/workspace/capstone-trackb/data/gt_v2_5.xlsx`, sheet `Data` (532 records).
Controlled vocabulary: `vocab/controlled-vocabulary.json` version 1.0.0.

This is a read-only comparison. The GT file was not modified.

Vocabulary differences: **0** (merges still present in GT, dropped labels still present in GT, or new GT labels not in the vocabulary).

## Matches (same label in GT and the vocabulary)

- **intent** (8): capability_match, coverage_limits, docs_how_to, human_handoff, pricing_comparison, pricing_quote, sales_qualification, troubleshooting
- **sub_intent** (31): accuracy_question, accuracy_regression, billing_dispute, billing_incident, billing_question, capability_fit, capability_matching, capability_question, competitive_comparison, contract_request, coverage_error, coverage_question, data_quality, discovery_qualification, error_resolution, free_tier_question, integration_question, licensing_fit, limits_question, migration_question, parameter_question, parameter_troubleshooting, performance_question, policy_question, pricing_comparison, pricing_estimate, pricing_quote, production_incident, response_fields, security_incident, solution_design
- **bucket** (10): capabilitycompare, coveragecompare, docs, history, interpretation, limitscompare, ownership, pricecompare, qualification, updates
- **api** (4): autocomplete, directions, distance_matrix, reverse_geocode
- **primary_team** (2): Sales, Support
- **providers** (6): Google Maps Platform, Mapbox, Mappls (MapmyIndia), OSM Nominatim, OSRM, Ola Maps
- **tools** (4): calculator, doc_search, escalate_ticket, update_record
- **owners** (4): Account team (Sales), Maps engineering, Support L1, Support L2
- **severities** (4): SEV1, SEV2, SEV3, SEV4

## Merged (GT label → vocabulary label)

- None.

## Dropped (present in GT, retired from the copilot vocabulary)

- None.

## New in GT v2.5 and not in the vocabulary

- None. Every distinct GT v2.5 intent, sub_intent, bucket, API, team, owner, severity, provider and tool value is accounted for. There are 0 vocabulary differences.
