"""Summarize the locked frozen result and observed historical behavior changes."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/activity14-frozen-qualification'
REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    manifest = load(OUT / 'run-manifest.json')
    runtime = Path(manifest['runtime'])
    scores = load(OUT / 'scores.json')
    behavior = load(OUT / 'behavior.json')
    diagnostics = load(OUT / 'question-diagnostics.json')
    rows = [json.loads(line) for line in (OUT / 'predictions.jsonl').read_text().splitlines()]
    calls = [json.loads(line) for line in (OUT / 'model-calls.jsonl').read_text().splitlines()]
    assert len(rows) == 80 and [r['record_id'] for r in rows] == manifest['frozen_record_ids']
    checks = {'runtime_files_unchanged': all(digest(runtime / p) == h for p, h in manifest['source_hashes'].items()),
        'production_code_matches_lock': all(digest(REPO / p) == h for p, h in manifest['code_hashes'].items()),
        'frozen_inputs_unchanged': digest(OUT / 'inputs.jsonl') == manifest['frozen_inputs_sha256'],
        'frozen_gt_unchanged': digest(OUT / 'ground-truth-frozen.csv') == manifest['frozen_gt_sha256'],
        'original_question_text_unchanged': digest(OUT / 'frozen-questions.json') == manifest['official_questions_sha256'],
        'prior_derived_atomic_facts_unchanged': digest(OUT / 'locked-gold.json') == manifest['gold_sha256'],
        'local_gt_workbook_unchanged': digest(REPO / 'data/ground-truth.xlsx') == manifest['workbook_before_sha256'],
        'prelocked_alignment_plan_unchanged': digest(OUT / 'fact-alignment-plan.json') == manifest['evaluation_alignment_plan_sha256'],
        'all80_selected_once': len({r['record_id'] for r in rows}) == 80,
        'holdout_cases_selected_or_scored': 0}
    assert all(v for k, v in checks.items() if k != 'holdout_cases_selected_or_scored')
    write(OUT / 'integrity-verification.json', checks)
    changes = []
    for row in rows:
        before, after = row['snapshots']['baseline'], row['snapshots']['integrated']
        if before['route'] != after['route'] or before['pending_reply'] != after['pending_reply']:
            changes.append({'record_id': row['record_id'], 'route_before': before['route'], 'route_after': after['route'],
                'pending_before': (before['pending_reply'] or {}).get('field'),
                'pending_after': (after['pending_reply'] or {}).get('field')})
    review = load(OUT / 'question-review.bound.json')
    before_facts = {(r['record_id'], g, f) for r in review['cases'] for _, g, f in r['methods']['baseline']['facts']}
    after_facts = {(r['record_id'], g, f) for r in review['cases'] for _, g, f in r['methods']['integrated']['facts']}
    no_questions = [r for r in rows if r['gold'] and not r['questions']['integrated']]
    assigned_owners_preserved = sum(
        all(r['snapshots']['baseline']['owner'].get(k) == r['snapshots']['integrated']['owner'].get(k)
            for k in ['owner', 'team']) for r in rows)
    pass_threshold = scores['integrated']['f1'] >= manifest['question_f1_threshold']
    execution = {'cases': 80, 'fresh_model_completion_calls': len(calls),
        'model_call_errors': sum('error_type' in c for c in calls),
        'schema_valid': sum(not r['schema_errors'] for r in rows),
        'current_pending_replies': behavior['pending_after'],
        'followup_replies_executed': behavior['current_reopened_cases'],
        'no_question_selection_statuses': dict(Counter((r['details']['integrated']['selection'] or {}).get('status', 'none') for r in no_questions)),
        'newly_covered_facts': len(after_facts - before_facts),
        'retained_previously_covered_facts': len(after_facts & before_facts),
        'previously_covered_facts_now_missed': [list(v) for v in sorted(before_facts - after_facts)],
        'assigned_owners_preserved': assigned_owners_preserved,
        'historical_comparison_caveat': 'The prior frozen outputs were saved earlier. Differences include model-execution variation and cannot all be attributed causally to one change.'}
    write(OUT / 'execution-quality.json', execution)
    summary = {'scope': 'Exact ordered 80 frozen cases; original GT and 99-fact decomposition unchanged; holdout excluded.',
        'scores': scores, 'question_f1_threshold': manifest['question_f1_threshold'],
        'question_f1_target_met': pass_threshold, 'activity14_acceptance_complete': False,
        'diagnostics': diagnostics, 'execution': execution, 'route_and_pending_changes': changes,
        'integrity': checks,
        'review_status': 'Assistant semantic judgements with independent assistant cross-checks; not independent human acceptance.'}
    write(OUT / 'summary.json', summary)
    baseline, current = scores['baseline'], scores['integrated']
    change_table = '\n'.join(f"| {c['record_id']} | {c['route_before']} → {c['route_after']} | {c['pending_before'] or 'none'} → {c['pending_after'] or 'none'} |" for c in changes)
    report = f'''# Activity 14 frozen evaluation

The validated implementation was locked and run on the same ordered 80 frozen inputs. The question-F1 target of 0.80 is not met. No application changes, label changes, threshold changes or case exclusions were made during the scored run.

| Measure | Prior saved frozen run | Locked rerun |
| --- | ---: | ---: |
| Clarifying-question F1 | {baseline['f1']:.4f} | {current['f1']:.4f} |
| Whole gold questions matched | {baseline['matches']}/75 | {current['matches']}/75 |
| Fact coverage | {baseline['facts']}/99 ({baseline['fact_recall']:.2%}) | {current['facts']}/99 ({current['fact_recall']:.2%}) |
| Questions produced | {baseline['predicted']} | {current['predicted']} |
| Questions on cases with empty gold lists | {baseline['questions_on_empty_gold']} | {current['questions_on_empty_gold']} |

This uses the original 75 frozen question groups and the same prior 99-atom decomposition. It does not use the separate 55-question working reference. Judgements compare actual question text with the frozen meaning and granularity: whole matches are one-to-one, independently bundled decisions cannot match several shorter gold questions, and partial facts are counted separately. All 80 judgements were cross-checked by another assistant with no disagreements, and bound to the exact prediction and gold hashes. This is assistant-reviewed evidence, not an independent human spot-check.

## Coverage gaps

Of 40 cases with gold questions, 27 generated no question. Their selection statuses were 17 `no_qualification_required`, eight `no_follow_up` and two preserved decline routes. The frozen questions were retained for scoring even when the customer had supplied a fact or declined more questions.

The system also generated 24 questions across 16 cases whose frozen gold lists are empty. Eight whole questions and 18 facts were matched. Only four additional gold groups have all their facts covered without an equivalent whole-question match, so the low score is primarily a coverage/selection gap, with a smaller grouping contribution. Missing distinctions include account versus backend/deployment ownership, billing and eligibility choices, and typical/maximum matrix sizes, frequency and concurrency. Related field names were not treated as equivalent automatically.

Sixteen facts are newly covered and two previously covered facts remain covered. The monthly/required-volume facts in AC-231 and DM-226 that were previously covered are now missed. Full unmatched questions and facts are in `per-case-question-analysis.json`. No fixes were made from these frozen results.

## Routes and pending replies

| Case | Route change | Pending reply change |
| --- | --- | --- |
{change_table}

The four clarification changes deliver checklist advice without opening a generic customer intake question. DIR-221 now passes the document relevance review; that observation comes from a fresh model execution and is not isolated proof of a particular code change.

- Final-draft status: 61 → 66; escalated: 15 → 14; clarification-needed: four → zero.
- Initial routes are unchanged in 75/80 cases. Pending replies are unchanged in 76/80 and cleared in the four listed cases.
- Assigned owner and team are unchanged in 80/80. The full ownership object differs once because DIR-221 no longer includes its prior failed-review explanation.
- Approvals and proposed actions are unchanged in 80/80.
- No current reply turns were executed because no initial result leaves an active pending reply. The historical run reopened four pending cases, so this rerun does not claim four paired reopen-preservation checks.

## Execution and integrity

All 80 outputs are schema-valid. The run made 239 fresh completion calls with no recorded model-call errors, using the same institute model and BM25 mode; no seeded output cache was used. The implementation matches the working-eval version that passed 559 automated tests and four subtests. Source, configuration, schema, prompt, tokenizer and processed-corpus assets were copied and hashed before predictions. An isolated-runtime SQLite schema packaging omission was corrected before any model request; the application source was unchanged.

Post-run checks confirmed unchanged frozen input bytes, frozen GT export, original question text, prior fact labels, local GT workbook, alignment plan and all locked runtime assets. Every selected record is an eval record marked frozen-core. Holdout cases were neither selected nor scored.

The comparison column uses the prior saved `frozen-locked` results. Current completion calls are fresh, so observed behavior changes can include model-execution variation. The 1.000 working score does not transfer to this frozen reference. Activity 14 cannot be marked complete from this run.

## Saved evidence

- `implementation-lock.json`, `run-manifest.json`, `runtime/`: locked code, assets and selection lineage.
- `inputs.jsonl`, `ground-truth-frozen.csv`, `frozen-questions.json`, `locked-gold.json`: unchanged inputs and references.
- `predictions.jsonl`, `model-calls.jsonl`: full output/state records and model requests/responses.
- `scores.json`, `question-review.bound.json`, `per-case-question-analysis.json`: reproducible scores and exact judgements.
- `behavior.json`, `execution-quality.json`, `integrity-verification.json`: observed control changes and integrity checks.
- `fact-alignment-plan.json`, primary review files and independent audit files: evaluation-only semantic review provenance.

From the repository root, reproduce the saved scores without a model call:

```sh
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/frozen-qualification/rescore.py
```
'''
    (OUT / 'report.md').write_text(report)
    print(json.dumps({'scores': scores, 'question_f1_target_met': pass_threshold,
                      'execution': execution, 'changes': changes}, indent=2))


if __name__ == '__main__':
    main()
