# Working-eval failure analysis

Candidate v1 scores **46.44% question F1** and **48.78% fact coverage** on the unchanged 317-case reference. The 80% target is not met. This audit changes no labels, production code or scores.

## Questions on empty references

The 50 empty-gold cases contain 67 questions. Review classified **36 as clearly unnecessary**, **24 as defensible missing-fact requests**, and **7 as answer-first, conditional follow-ups**. Empty gold alone does not prove a question is wrong.

- Repeated facts: asking about storage after “no storage”, or after “must store 300,000 results”; asking the selected driving/two-wheeler mode again.
- Operation mismatch: asking autocomplete debouncing while pricing a fixed count of Place Details calls; asking Google project eligibility in a Mapbox-only quote.
- Missing dependency gates: input format is asked for an already-counted monthly matrix-element quote, although it affects request feasibility rather than that price.
- Defensible diagnostics include failing matrix pairs, actual coordinates/filters, request restrictions and renderer-versus-API checks. Pricing geography can also be genuinely missing.

## Missed positive references

Of 66 unmatched gold groups, 23 clear supplied-fact/proceed-instruction conflicts are excluded from causal diagnosis only. The primary score still includes them. Of the 43 remaining groups, 14 already require materiality review and 29 are unflagged.

Genuine gaps include billing/account restoration context, offensive prediction examples, debounce intervals, Android SDK/REST and certificate context, via coordinates, traffic-metadata parameters, key-exposure impact, request-rate facts, commercial handoff details, usage exports, matrix shape and language-specific result granularity.

In some misses, the model proposes a useful decision but the policy allows only `none` or rejects the proposal as unsupported. These cases point to gaps in the shared catalogue and dispatch rules; they do not show that the model misunderstood every enquiry.

## Reference-policy conflict

All 52 diagnostic working cases had empty original question lists. Their separately reviewed reference adds 10 positive groups. The earlier 1.00 score therefore measured a different reference policy. The 36 qualification cases similarly contain 65 original groups versus 55 reviewed groups. These references must remain separately named and scored.

## Next correction

Use one product/operation/task contract to decide which customer facts can still change the requested answer. Bind compact supplied facts, mark documented remedies as resolved, and select only unresolved requirements from a shared diagnostic and qualification catalogue. Keep legitimate handoff facts available while preserving approval and pending-reply behaviour.

Reconcile reference policy through a separate, versioned review. The target is not proven impossible under the original labels, but this run cannot be called passing. Repeating known facts or removing defensible diagnostics to manufacture a higher score would reduce product quality.

Source hashes, all 67 question assessments, missed-group details and reference-overlap records are in `failure-analysis.json`. This is assistant analysis on working-eval only; frozen and holdout cases were excluded.
