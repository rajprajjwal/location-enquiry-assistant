"""Explain primary-reference errors without changing references or production behaviour."""
from collections import Counter
import hashlib
import json
from pathlib import Path

REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
OUT = REPO / 'copilot/response_drafting/results/activity-14/workflow-review'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def judgement(assessment, category, reason):
    return {'assessment': assessment, 'cause': category, 'reason': reason}


def main():
    gold_path, prediction_path = OUT / 'original-working-reference.json', OUT / 'candidate/predictions.jsonl'
    gold = {r['record_id']: r for r in json.loads(gold_path.read_text())['cases']}
    rows = {r['record_id']: r for r in map(json.loads, prediction_path.read_text().splitlines())}
    reviews = {r['record_id']: r['methods']['candidate'] for r in json.loads((OUT / 'candidate-bound-review.json').read_text())['cases']}
    conflicts_path = OUT / 'reference-conflicts.json'
    conflicts = json.loads(conflicts_path.read_text())
    clear = {(r['record_id'], r['gold_question_index'] + 1): r for r in conflicts['findings'] if r['classification'] != 'needs_review'}
    possible = {(r['record_id'], r['gold_question_index'] + 1): r for r in conflicts['findings'] if r['classification'] == 'needs_review'}
    annotations = {}

    def add(ids, *decisions):
        for suffix in ids.split():
            annotations['GT-LBS-' + suffix] = list(decisions)

    U, D, C = 'clearly_unnecessary', 'defensible_missing_fact', 'conditional_answer_first'
    add('AC-026 AC-027',
        judgement(C, 'requested_billing_options', 'The user asks for cost per billing option; show documented alternatives rather than requiring a terminating-call choice first.'),
        judgement(U, 'quantity_already_fixed', 'The number of requests per session is explicitly given; debouncing cannot change that stated request-count scenario.'))
    add('AC-035', judgement(D, 'billing_diagnostic', 'A session token alone does not prove valid session termination; the terminating call can explain per-request billing.'),
        judgement(U, 'wrong_decision_dependency', 'Debouncing affects volume, not why a token-bearing session is billed per request.'))
    add('AC-044', judgement(U, 'supplied_fact_reasked', 'The final Place Details call is explicitly part of the question.'),
        judgement(U, 'documented_rule', 'Whether keys from different projects share a billed session is a documented eligibility rule, independent of keystroke debouncing.'))
    add('AC-047', judgement(C, 'documented_remedy_before_reproduction', 'The draft already retrieves includeQueryPredictions and includedRegionCodes conditions. Explain these first; request the body if those settings do not resolve the reported failure.'))
    add('AC-049', judgement(U, 'explicit_scenario_reasked', 'The conditional scenario already states session termination with Place Details Pro.'))
    add('AC-053', judgement(C, 'documented_remedy_before_reproduction', 'The reported error names an empty input. Give the required-input remedy first; the response error is already supplied, and a request is useful only if the issue persists.'))
    add('AC-069', judgement(D, 'request_reproduction', 'An exact redacted input/request can establish the actual pasted-input length and endpoint parameters.'))
    add('AC-094', judgement(U, 'optional_qualification_on_documentation', 'POI-versus-address preferences are not needed to explain country restriction parameters across providers.'))
    add('AC-116 AC-117 AC-118', judgement(U, 'operation_mismatch', 'The user explicitly prices Ola Place Details calls after selection; asking whether that call occurs repeats the priced operation.'),
        judgement(U, 'operation_mismatch', 'Debouncing preceding autocomplete calls does not determine the price of the stated Place Details call count.'))
    add('AC-122 AC-123', judgement(U, 'provider_product_mismatch', 'A Google-style Place Details session question is applied to an Ola-versus-Mapbox autocomplete comparison.'),
        judgement(D, 'keystrokes_not_http_calls', 'Keystrokes do not establish how many HTTP calls are sent after debouncing; this can affect a per-request comparison.'))
    add('AC-125', judgement(U, 'optional_qualification_on_documentation', 'Published free usage and restrictions can be compared before asking a new hosting-preference question.'))
    add('AC-217', judgement(U, 'documented_rule', 'The question asks whether HTTP requests or keystrokes are billed, not for a personalized monthly estimate.'))
    add('AC-225', judgement(C, 'documented_remedy_before_reproduction', 'Answer the documented retrieve-session parameter requirement first; a redacted actual request is useful if validation still fails.'))
    add('DIR-057', judgement(D, 'request_reproduction', 'The actual URL is needed to distinguish encoded URL length, waypoint representation and API restrictions.'))
    add('DIR-064', judgement(C, 'documented_remedy_before_reproduction', 'The origin value and exact error are already given. Explain coordinate order/format first; request the full call only for an unresolved remainder.'))
    add('DIR-088', judgement(D, 'diagnostic_isolation', 'An isolated failing call distinguishes a burst-specific failure from a continuing quota or request problem.'))
    add('DIR-097', judgement(D, 'renderer_vs_api', 'Whether the API returns a route separates rendering replacement from a server-side waypoint failure.'))
    add('DIR-098', judgement(U, 'generic_intake_route', 'Operating region does not resolve the requested waypoint-order optimization capability; a broad sales label triggered a generic blocking question.'))
    add('DIR-106', judgement(D, 'request_reproduction', 'HTTP 422 alone does not establish which parameter or regional condition failed; the actual request and response body are useful.'))
    add('DIR-110', judgement(C, 'documented_limit_before_reproduction', 'The named repeated long route supports a distance-limit explanation first. Ask for the request only if the documented cap does not explain the failure; this run produced no draft.'))
    add('DIR-117', judgement(U, 'price_insensitive_capability', 'The stated Mapbox Directions request price does not require choosing a traffic profile first.'),
        judgement(U, 'supplied_fact_reasked', 'Driving is explicitly specified.'),
        judgement(U, 'provider_product_mismatch', 'Google project eligibility is irrelevant to a Mapbox-only quote.'))
    add('DIR-124', judgement(U, 'price_insensitive_capability', 'The named Google two-wheeler Routes product already determines the relevant SKU; do not require a separate feature-selection discussion to quote it.'),
        judgement(U, 'supplied_fact_reasked', 'Two-wheeler travel mode is explicitly specified.'),
        judgement(U, 'provider_product_mismatch', 'The user chose Routes API; a legacy-project eligibility question is not needed for this quote.'))
    add('DM-049', judgement(D, 'failed_input_example', 'A failing origin/destination pair is material to an element-level NOT_FOUND diagnosis.'))
    add('DM-061 RG-034 RG-086 RG-102', judgement(D, 'request_reproduction', 'The observed denial has no confirmed complete request-level cause; a redacted as-sent example can verify endpoint, restrictions and authentication context.'))
    add('DM-069', judgement(U, 'documented_billing_unit', 'Per-request versus per-pair billing is a provider rule, independent of the customer traffic/travel-mode preference.'))
    add('DM-114 DM-115 DM-116 DM-120 DM-121', judgement(U, 'price_insensitive_input_format', 'The billable monthly element count and product are already supplied; input representation affects request feasibility, not this element-price calculation.'))
    add('DM-225', judgement(U, 'documented_limit_scope', 'The question supplies a transit matrix shape. Explain the transit element cap and batching; a generic input-format quote question does not resolve that cap.'))
    add('RG-062', judgement(D, 'request_reproduction', 'The request type/filter context can determine whether limit=5 is valid; the query does not establish that the required type is absent.'))
    add('RG-065', judgement(D, 'rate_diagnostic', 'A reported 429 needs request/retry context, although aggregate rate and retry headers would be more targeted than the generic request template.'))
    add('RG-096', judgement(D, 'licensing_requirement', 'Result storage affects which free or temporary products can be recommended.'),
        judgement(D, 'usage_policy_requirement', 'User-triggered versus periodic tracking affects public-service suitability.'))
    add('RG-098 RG-099 RG-100 RG-101', judgement(D, 'failed_input_example', 'Actual coordinates and filters are material to a specific ZERO_RESULTS diagnosis; original empty labels do not make the diagnostic request inherently wrong.'))
    add('RG-117 RG-118 RG-119', judgement(U, 'negative_fact_not_bound', 'The query explicitly says display only, no storage, but storage is asked again.'),
        judgement(D, 'pricing_geography_requirement', 'Billing country and primary usage geography can change the applicable pricing schedule and are not supplied.'))
    add('RG-120 RG-121', judgement(U, 'numeric_object_not_bound', 'The query explicitly requires storing a stated number of results. A number between store and results defeats the narrow requirement extractor.'))

    empty = []
    for rid, row in rows.items():
        if row['questions'] and not gold[rid]['questions']:
            assert rid in annotations and len(annotations[rid]) == len(row['questions']), rid
            empty.append({'record_id': rid, 'query': row['query'], 'history': row['history'],
                          'selection_status': row['result'].get('follow_up_selection', {}).get('status'),
                          'questions': [{'index': i, 'text': text, **decision}
                                        for i, (text, decision) in enumerate(zip(row['questions'], annotations[rid], strict=True), 1)]})
    assert len(empty) == 50 and sum(len(row['questions']) for row in empty) == 67
    assessments = Counter(q['assessment'] for row in empty for q in row['questions'])
    causes = Counter(q['cause'] for row in empty for q in row['questions'])
    missing, excluded = [], []
    for rid, label in gold.items():
        matched = {g for _, g in reviews[rid]['whole']}
        for index, question in enumerate(label['questions'], 1):
            if index in matched:
                continue
            if (rid, index) in clear:
                excluded.append({'record_id': rid, 'gold_question_index': index,
                                 'classification': clear[rid, index]['classification']})
                continue
            row = rows[rid]
            selection = row['result'].get('follow_up_selection', {})
            missing.append({'record_id': rid, 'gold_question_index': index, 'question': question['question'],
                            'reference_materiality_needs_review': (rid, index) in possible,
                            'selection_status': selection.get('status'), 'allowed_decisions': selection.get('allowed_decisions'),
                            'model_proposal': selection.get('proposal'), 'predicted_questions': row['questions']})
    prior = {}
    for name, path in [('reviewed52', REPO / 'copilot/response_drafting/results/activity-14/request-denied/locked-gold.json'),
                       ('reviewed36', REPO / 'copilot/response_drafting/results/activity-14/clarification-routing/reviewed-reference.json')]:
        data = json.loads(path.read_text())
        selected = [r for r in data['cases'] if r['record_id'] in gold]
        prior[name] = {'source_sha256': digest(path), 'cases': len(selected),
                       'original_question_groups': sum(len(gold[r['record_id']]['questions']) for r in selected),
                       'reviewed_question_groups': sum(len(r['questions']) for r in selected),
                       'original_positive_cases': sum(bool(gold[r['record_id']]['questions']) for r in selected),
                       'reviewed_positive_cases': sum(bool(r['questions']) for r in selected),
                       'polarity_changed_cases': [{'record_id': r['record_id'], 'original_questions': len(gold[r['record_id']]['questions']),
                                                  'reviewed_questions': len(r['questions'])} for r in selected
                                                 if bool(r['questions']) != bool(gold[r['record_id']]['questions'])]}
    analysis = {'scope': 'Read-only causal audit of candidate v1 on all 317 fixed working-eval; primary gold and primary score unchanged.',
                'review_kind': 'Assistant analysis, not independent human adjudication.',
                'source_sha256': {'candidate_predictions': digest(prediction_path), 'original_reference': digest(gold_path),
                                  'bound_review': digest(OUT / 'candidate-bound-review.json'), 'reference_conflicts': digest(conflicts_path)},
                'primary_score': json.loads((OUT / 'candidate-score.json').read_text())['overall'],
                'empty_gold': {'cases': 50, 'questions': 67, 'question_assessments': dict(assessments), 'by_cause': dict(causes), 'cases_detail': empty},
                'missed_gold_groups': {'total': len(missing) + len(excluded), 'clear_conflicts_excluded_from_causal_analysis_only': len(excluded),
                                       'remaining': len(missing), 'remaining_materiality_needs_review': sum(row['reference_materiality_needs_review'] for row in missing),
                                       'remaining_unflagged': sum(not row['reference_materiality_needs_review'] for row in missing),
                                       'excluded_detail': excluded, 'remaining_detail': missing},
                'prior_reference_overlap': prior,
                'architecture_causes': [
                    'Task dispatch still chooses broad API/intent menus without a product, priced operation, requested output and resolved-evidence dependency gate.',
                    'Suppression checks recognize some assertions but miss compact negative phrases and numeric objects, allowing known facts to be asked again.',
                    'Documented fixes and conditional branches are not represented as resolved or answerable decisions, so reproduction templates can survive after sufficient guidance is retrieved.',
                    'Diagnostic policy recognizes a narrow set of enums and error codes; genuine billing, quality, identity and security handoff facts are discarded as none or unsupported.',
                    'The API catalogue lacks several material matrix-size, output-granularity and storage-duration requirements outside the small qualification development subset.',
                    'Original acceptance questions and separately reviewed working questions implement different policies about repeated facts and useful diagnostic follow-ups.'],
                'next_fixes': [
                    'Unify product/operation/task and fact dependency contracts before selecting questions. Quote fixed billable quantities without unrelated capability intake; keep published-rule questions as documented answers.',
                    'Add evidence-bound extraction for compact no-storage statements, quantified stored results, explicit selected modes and terminating calls; preserve actual/scenario distinction.',
                    'Use a documented-remedy resolution gate: answer supported parameter or limit remedies first and ask reproduction only for the unresolved decision.',
                    'Expand one shared diagnostic/handoff requirement catalogue for actual symptoms, including request rate, debounce interval, platform restrictions, failing samples, billing exports and security impact. Preserve sandbox approvals.',
                    'Review the versioned reference policy separately. Continue primary unchanged scores; do not claim passing by substituting the reviewed52/36 labels.'],
                'target_statement': 'Candidate v1 F1 is 46.44%, below 80%. The target is not proven mathematically impossible under the original reference; however current performance cannot be called passing, and suppressing defensible diagnostics or repeating supplied facts merely to match inconsistent labels would be a regression.',
                'frozen_cases': 0, 'holdout_cases': 0, 'label_changes': 0, 'production_changes': 0}
    (OUT / 'failure-analysis.json').write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + '\n')
    lines = ['# Working-eval failure analysis', '',
             'Candidate v1 scores **46.44% question F1** and **48.78% fact coverage** on the unchanged 317-case reference. The 80% target is not met. This audit changes no labels, production code or scores.', '',
             '## Questions on empty references', '',
             f'The 50 empty-gold cases contain 67 questions. Review classified **{assessments[U]} as clearly unnecessary**, **{assessments[D]} as defensible missing-fact requests**, and **{assessments[C]} as answer-first, conditional follow-ups**. Empty gold alone does not prove a question is wrong.', '',
             '- Repeated facts: asking about storage after “no storage”, or after “must store 300,000 results”; asking the selected driving/two-wheeler mode again.',
             '- Operation mismatch: asking autocomplete debouncing while pricing a fixed count of Place Details calls; asking Google project eligibility in a Mapbox-only quote.',
             '- Missing dependency gates: input format is asked for an already-counted monthly matrix-element quote, although it affects request feasibility rather than that price.',
             '- Defensible diagnostics include failing matrix pairs, actual coordinates/filters, request restrictions and renderer-versus-API checks. Pricing geography can also be genuinely missing.', '',
             '## Missed positive references', '',
             f'Of 66 unmatched gold groups, 23 clear supplied-fact/proceed-instruction conflicts are excluded from causal diagnosis only. The primary score still includes them. Of the 43 remaining groups, 14 already require materiality review and 29 are unflagged.', '',
             'Genuine gaps include billing/account restoration context, offensive prediction examples, debounce intervals, Android SDK/REST and certificate context, via coordinates, traffic-metadata parameters, key-exposure impact, request-rate facts, commercial handoff details, usage exports, matrix shape and language-specific result granularity.', '',
             'The model sometimes proposes a useful decision, but policy permits only `none` or rejects the proposal as unsupported. This is a shared catalogue/dispatch problem rather than evidence that the model failed to understand every enquiry.', '',
             '## Reference-policy conflict', '',
             'All 52 diagnostic working cases had empty original question lists. Their separately reviewed reference adds 10 positive groups. The earlier 1.00 score therefore measured a different reference policy. The 36 qualification cases similarly contain 65 original groups versus 55 reviewed groups. These references must remain separately named and scored.', '',
             '## Next correction', '',
             'Use one product/operation/task contract to decide which customer facts can still change the requested answer. Bind compact supplied facts, mark documented remedies as resolved, and select only unresolved requirements from a shared diagnostic and qualification catalogue. Keep legitimate handoff facts available while preserving approval and pending-reply behaviour.', '',
             'Reconcile reference policy through a separate, versioned review. The target is not proven impossible under the original labels, but this run cannot be called passing. Repeating known facts or removing defensible diagnostics to manufacture a higher score would reduce product quality.', '',
             'Source hashes, all 67 question assessments, missed-group details and reference-overlap records are in `failure-analysis.json`. This is assistant analysis on working-eval only; frozen and holdout cases were excluded.']
    (OUT / 'failure-analysis.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'empty_gold_question_assessments': dict(assessments),
                      'missed_groups': analysis['missed_gold_groups'] | {'remaining_detail': None, 'excluded_detail': None},
                      'overlap': {k: {x: v[x] for x in ['cases', 'original_question_groups', 'reviewed_question_groups']} for k, v in prior.items()}}, indent=2))


if __name__ == '__main__':
    main()
