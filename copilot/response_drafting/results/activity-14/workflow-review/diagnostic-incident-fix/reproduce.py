"""Reproduce the isolated 52-case diagnostic-policy regression without live calls."""
import hashlib
import json
from pathlib import Path
import sys
import types
from unittest.mock import patch


def main():
    directory = Path(__file__).resolve().parent
    project = next(parent for parent in directory.parents if (parent / 'copilot/diagnostics/policy.py').is_file())
    sys.path.insert(0, str(project))
    from copilot.diagnostics.facts import build_diagnostic_state
    from copilot.diagnostics.policy import allowed_decisions
    from copilot.diagnostics.planning import plan_staff_follow_up
    from copilot.enquiry_interpretation.rules import extract
    from tests.enquiry_workflow.test_additional_diagnostic_evidence import result_for, client_for

    manifest = json.loads((directory / 'scope-hashes.json').read_text())
    baseline = directory / 'before-source/copilot/diagnostics/policy.py'
    baseline_bytes = baseline.read_bytes()
    if hashlib.sha256(baseline_bytes).hexdigest() != manifest['before_sha256']['copilot/diagnostics/policy.py']:
        raise ValueError('Baseline policy hash mismatch.')
    inputs_path = directory / 'inputs52.json'
    if hashlib.sha256(inputs_path.read_bytes()).hexdigest() != manifest['inputs52_sha256']:
        raise ValueError('Working input hash mismatch.')
    for name, expected in manifest['owned_sha256'].items():
        if hashlib.sha256((project / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Reviewed source changed: {name}')
    previous = types.ModuleType('previous_diagnostic_policy')
    previous.__package__ = 'copilot.diagnostics'
    exec(compile(baseline_bytes, str(baseline), 'exec'), previous.__dict__)
    rows = json.loads(inputs_path.read_text())
    allowlist = {row['record_id'] for row in json.loads((directory.parent / 'inputs317.json').read_text())}
    if len(rows) != 52 or any(row['record_id'] not in allowlist for row in rows):
        raise ValueError('The regression inputs must be the 52 approved working-eval cases.')
    results = []
    for row in rows:
        enquiry = {key: row[key] for key in ('query', 'history')}
        query = enquiry['query']
        api = extract(enquiry['history'], query)['unique_api']
        state = build_diagnostic_state(enquiry)
        before = previous.allowed_decisions(state, query, api, enquiry=enquiry)
        after = allowed_decisions(state, query, api, enquiry=enquiry)
        original = result_for(query, api=api)
        with patch('copilot.diagnostics.planning.allowed_decisions', previous.allowed_decisions):
            old = plan_staff_follow_up(original, enquiry, client=client_for())
        new = plan_staff_follow_up(original, enquiry, client=client_for())
        unchanged = all(old.get(key) == new.get(key) == original.get(key) for key in (
            'status', 'pending_reply', 'clarifying_questions', 'proposed_actions'))
        unchanged = unchanged and all(old['outputs'].get(key) == new['outputs'].get(key) == original['outputs'].get(key)
                                      for key in ('responsible_role', 'next_action', 'proposed_record_update'))
        results.append({'record_id': row['record_id'], 'api': api, 'before_allowed': before,
                        'after_allowed': after, 'menu_unchanged': before == after,
                        'fixture_controls_unchanged': unchanged})
    summary = {'working_cases': len(results), 'menus_unchanged': sum(row['menu_unchanged'] for row in results),
               'fixture_controls_unchanged': sum(row['fixture_controls_unchanged'] for row in results),
               'live_calls': 0, 'frozen_cases': 0, 'holdout_cases': 0,
               'method': 'Isolated policy comparison with fixed model proposals and fixture controls, not live route accuracy or F1.'}
    (directory / 'reproduced-working52-policy-regression.json').write_text(json.dumps({'summary': summary, 'cases': results}, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    if summary['menus_unchanged'] != 52 or summary['fixture_controls_unchanged'] != 52:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
