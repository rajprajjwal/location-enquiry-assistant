"""Review a fixed working prefix and replay saved interpretation replies without model calls."""
import hashlib
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
sys.path.insert(0, str(REPO))
from copilot.enquiry_interpretation.postcheck import first_json_object, postcheck, strip_think

BASELINE = REPO / 'copilot/response_drafting/results/activity-14/workflow-review/baseline'
PREFIX = 78
NOTES = {
    'GT-LBS-AC-003': {'intent': 'Ambiguous sales-qualification versus capability boundary. The existing hosting follow-up is appropriate; do not change behaviour merely to force the intent label.'},
    'GT-LBS-AC-072': {'api': 'Reverse geocoding is not supported by the /category-search enquiry. The original autocomplete bucket is a broad product grouping; category search is not itself type-ahead. Do not invent an autocomplete alias from the record ID.'},
    'GT-LBS-AC-082': {'api': 'Explicit Nominatim search is not reverse geocoding, but the query does not say interactive type-ahead. Original autocomplete label is scope-ambiguous; preserve primary scoring.'},
    'GT-LBS-AC-084': {'api': 'Nominatim forward search is not reverse geocoding. No typing or suggestion requirement is stated, so do not globally map the provider to autocomplete.'},
    'GT-LBS-AC-085': {'api': 'Nominatim requests and a missing User-Agent do not identify search versus reverse. Original API is not inferable from the supplied query; no record-specific correction.'},
    'GT-LBS-AC-091': {'api': 'Google Places search-box context provides a clear autocomplete cue. Fixed by a general product/operation alias.'},
    'GT-LBS-AC-092': {'intent': 'Clear capability question about session-pricing support, not a requested estimate. Current quote classification contributes two unnecessary staff questions about debouncing and Place Details.'},
    'GT-LBS-AC-094': {'intent': 'Docs-how-to versus comparative capability is a legitimate boundary. The blocking current-provider question is separately inappropriate for a request covering each provider.'},
    'GT-LBS-AC-099': {'intent': 'Original docs-how-to label is debatable: the user explicitly asks whether only one country is allowed. Coverage-limits is semantically defensible. Preserve the original label and report the conflict.'},
    'GT-LBS-AC-103': {'intent': 'Clear observed parameter malfunction: types only seems to work with establishment. Troubleshooting is supported more directly than capability matching.'},
    'GT-LBS-AC-109': {'intent': 'Original pricing-quote label is under-supported by the standalone question about needing session tokens. Docs-how-to is defensible; no price calculation or workload is requested.'},
    'GT-LBS-AC-204': {'intent': 'Clear per-request country-restriction capacity question. Coverage-limits is more specific than generic parameter guidance.'},
    'GT-LBS-AC-212': {'intent': 'Availability in Dubai is a geographic-coverage question; coverage-limits is more specific than a generic capability label.'},
    'GT-LBS-AC-218': {'intent': 'Permitted use of public Nominatim on every keystroke is an official usage-policy question, rather than a generic product capability. The current escalation also warrants separate grounding/relevance review.'},
    'GT-LBS-AC-219': {'api': 'Live address suggestions provide an explicit autocomplete cue. Fixed by a general interactive-suggestion alias.',
                      'intent': 'Original docs-how-to label is debatable because the user reports an integration that got blocked. Troubleshooting is semantically defensible; preserve the original label.'},
}


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def main():
    reference_path = OUT / 'working-interpretation-reference.json'
    reference = {row['record_id']: row for row in json.loads(reference_path.read_text())['cases']}
    lines = (BASELINE / 'predictions.jsonl').read_text().splitlines()[:PREFIX]
    rows = [json.loads(line) for line in lines]
    assert len(rows) == PREFIX and {row['record_id'] for row in rows} <= reference.keys()
    failures = []
    correct = {field: 0 for field in ('api', 'intent')}
    for row in rows:
        expected = reference[row['record_id']]
        actual = row['result']['diagnostic_context']['interpretation']
        bad = [field for field in correct if actual[field] != expected[field]]
        for field in correct:
            correct[field] += actual[field] == expected[field]
        if bad:
            failures.append({'record_id': row['record_id'], 'query': row['query'], 'history': row['history'],
                             'expected': {field: expected[field] for field in correct}, 'actual': actual,
                             'mismatched_fields': bad, 'assessment': NOTES[row['record_id']],
                             'route': row['snapshot']['route'], 'pending_reply': row['snapshot']['pending_reply'],
                             'staff_questions': row['questions']})
    audit = {'scope': 'First 78 completed baseline working-eval records; this is an autocomplete-heavy prefix, not a representative full-run score.',
             'records': PREFIX, 'correct': correct, 'failures': failures,
             'reference_sha256': digest_bytes(reference_path.read_bytes()),
             'prediction_prefix_sha256': digest_bytes(('\n'.join(lines) + '\n').encode()),
             'label_changes': 0, 'frozen_records': 0, 'holdout_records': 0}
    (OUT / 'working-interpretation-prefix-audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False) + '\n')

    responses = {}
    ids = {row['record_id'] for row in rows}
    for line in (BASELINE / 'model-calls.jsonl').open():
        record = json.loads(line)
        if record['record_id'] not in ids or not record.get('response'):
            continue
        text = record['response']['text']
        try:
            parsed = first_json_object(strip_think(text))
        except (ValueError, TypeError):
            continue
        if 'api' in parsed and 'intent' in parsed:
            responses.setdefault(record['record_id'], []).append(text)
    replay_rows = []
    for row in rows:
        rid = row['record_id']
        candidate = None
        for text in responses.get(rid, []):
            result = postcheck(text, query=row['query'], history=row['history'])
            if not result['errors']:
                candidate = result['output']
                break
        assert candidate is not None, rid
        actual = row['result']['diagnostic_context']['interpretation']
        replay_rows.append({'record_id': rid, 'baseline_api': actual['api'], 'candidate_api': candidate['api'],
                            'expected_api': reference[rid]['api'],
                            'raw_response_sha256': digest_bytes(text.encode()),
                            'intent_unchanged': candidate['intent'] == actual['intent']})
    replay = {'scope': 'Recorded classification-response component replay through changed API rules. No new model or end-to-end workflow execution.',
              'records': PREFIX, 'live_model_calls': 0,
              'baseline_api_correct': sum(row['baseline_api'] == row['expected_api'] for row in replay_rows),
              'candidate_api_correct': sum(row['candidate_api'] == row['expected_api'] for row in replay_rows),
              'intent_unchanged': sum(row['intent_unchanged'] for row in replay_rows),
              'changes': [row for row in replay_rows if row['baseline_api'] != row['candidate_api']],
              'records_detail': replay_rows,
              'rules_sha256': digest_bytes((REPO / 'copilot/enquiry_interpretation/rules.py').read_bytes()),
              'reference_sha256': audit['reference_sha256'],
              'prediction_prefix_sha256': audit['prediction_prefix_sha256'],
              'frozen_records': 0, 'holdout_records': 0}
    (OUT / 'api-cue-replay-prefix.json').write_text(json.dumps(replay, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'prefix': PREFIX, 'baseline_correct': correct, 'distinct_mismatches': len(failures),
                      'api_replay': [replay['baseline_api_correct'], replay['candidate_api_correct']],
                      'intent_unchanged': replay['intent_unchanged']}, indent=2))


if __name__ == '__main__':
    main()
