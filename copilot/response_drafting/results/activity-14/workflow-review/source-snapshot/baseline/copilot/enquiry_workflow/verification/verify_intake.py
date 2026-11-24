"""Verify saved working-eval intake facts without model calls or answer scoring."""
import argparse
import hashlib
import json
from pathlib import Path

from copilot.diagnostics.extraction import extract_supplied_facts
from copilot.diagnostics.facts import build_diagnostic_state
from copilot.enquiry_interpretation.postcheck import rules_only
from copilot.qualification.workload import scenario_volume_from_enquiry
from copilot.safety.pii import redact

ROOT = Path(__file__).resolve().parents[3]
DEFAULT = ROOT / 'copilot/enquiry_workflow/results/intake-review'
PROVIDER_FIELDS = {'provider', 'current_provider', 'mentioned_providers'}


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(directory):
    manifest = read(directory / 'manifest.json')
    for filename, expected in manifest['input_files_sha256'].items():
        if digest(directory / filename) != expected:
            raise ValueError(f'Input hash mismatch: {filename}')
    allowlist = {row['record_id']: row for row in read(directory / 'working-allowlist.json')}
    inputs = read(directory / 'inputs.json')
    if len(inputs) != len({row['record_id'] for row in inputs}):
        raise ValueError('Duplicate record IDs.')
    reference = {row['record_id']: row for row in read(directory / 'provider-reference.json')['records']}
    before = {row['record_id']: row['facts'] for row in read(directory / 'before-extraction.json')}
    if set(reference) != {row['record_id'] for row in inputs} or set(before) != set(reference):
        raise ValueError('Reference and baseline must bind exactly to the selected inputs.')
    results = []
    for row in inputs:
        rid = row['record_id']
        allowed = allowlist.get(rid)
        if not allowed or any(row[key] != allowed[key] for key in ('group', 'fold')):
            raise ValueError(f'Not an approved working-eval record/group/fold: {rid}')
        facts = extract_supplied_facts(row)
        state = build_diagnostic_state(row)
        values = {fact['field']: fact['value'] for fact in facts}
        interpreted = rules_only(query=row['query'], history=row.get('history', []), abstain_reason='Offline intake verification')['output']
        old = before[rid]
        expected = reference[rid]
        sources = {f'history[{i}]': redact(turn['text']) for i, turn in enumerate(row.get('history', [])) if turn['role'] == 'user'}
        sources['query'] = redact(row['query'])
        evidence_valid = all(
            fact['source'] in sources and sources[fact['source']][fact['start']:fact['end']] == fact['evidence']
            for fact in facts
        )
        other_before = [fact for fact in old if fact['field'] not in PROVIDER_FIELDS]
        other_after = [fact for fact in facts if fact['field'] not in PROVIDER_FIELDS]
        removed = [fact for fact in other_before if fact not in other_after]
        added = [fact for fact in other_after if fact not in other_before]
        scenario, scenario_source = scenario_volume_from_enquiry(row)
        old_values = {fact['field']: fact['value'] for fact in old}
        scenario_preserved = bool(
            scenario and old_values.get('workload') == scenario['requests_per_month']
            and old_values.get('workload_period') == 'month'
        )
        expected_change = not removed and not added or (
            not added and {fact['field'] for fact in removed} == {'workload', 'workload_period'}
            and scenario_preserved
        )
        results.append({
            'record_id': rid, 'group': row['group'], 'fold': row['fold'], 'facts': facts,
            'shared_state': state.model_dump(mode='json'),
            'provider_mentions_correct': set(values.get('mentioned_providers', [])) == set(expected['mentioned_providers']),
            'current_provider_scored': not expected['ambiguous'],
            'current_provider_correct': values.get('current_provider') == expected['current_provider'] if not expected['ambiguous'] else None,
            'provider_handoff_consistent': interpreted['qualification_details']['current_provider'] == values.get('current_provider'),
            'legacy_ambiguous_scalar': len(expected['mentioned_providers']) > 1 and 'provider' in old_values,
            'ambiguous_scalar_removed': len(expected['mentioned_providers']) <= 1 or 'provider' not in values,
            'evidence_valid': evidence_valid, 'non_provider_unchanged': other_before == other_after,
            'non_provider_change_expected': expected_change,
            'scenario_input_preserved': scenario_preserved if removed else None,
            'scenario_assumption': scenario, 'scenario_source': scenario_source,
        })
    scored = [row for row in results if row['current_provider_scored']]
    checks = {
        'provider_mentions_correct': sum(row['provider_mentions_correct'] for row in results),
        'current_provider_correct': sum(row['current_provider_correct'] for row in scored),
        'current_provider_scored': len(scored),
        'ambiguous_current_provider_excluded': len(results) - len(scored),
        'evidence_valid': sum(row['evidence_valid'] for row in results),
        'state_schema_valid': len(results),
        'provider_handoff_consistent': sum(row['provider_handoff_consistent'] for row in results),
        'legacy_ambiguous_scalars': sum(row['legacy_ambiguous_scalar'] for row in results),
        'ambiguous_scalar_checks_passed': sum(row['ambiguous_scalar_removed'] for row in results),
        'non_provider_unchanged': sum(row['non_provider_unchanged'] for row in results),
        'scenario_inputs_reclassified': sum(row['scenario_input_preserved'] is True for row in results),
        'unexpected_non_provider_changes': sum(not row['non_provider_change_expected'] for row in results),
    }
    passed = all(row['provider_mentions_correct'] and row['evidence_valid'] and row['ambiguous_scalar_removed'] and row['provider_handoff_consistent']
                 and row['non_provider_change_expected'] and row['current_provider_correct'] is not False for row in results)
    summary = {'passed': passed, 'records': len(results), 'frozen_records': 0, 'holdout_records': 0,
               'model_calls': 0, 'reference': 'Assistant-reviewed provider roles; eight ambiguous current-provider cases excluded.',
               'scope': 'Intake extraction and shared-state validation; not answer F1, live-model accuracy or all-route equivalence.',
               'checks': checks}
    return summary, results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT)
    options = parser.parse_args()
    summary, results = verify(options.directory)
    for name, value in [('scores.json', summary), ('after-extraction.json', results)]:
        (options.directory / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(summary, indent=2))
    if not summary['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
