"""Check the reviewed supplied/unknown facts without invoking the model."""
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/fact-binding-working'
manifest = json.loads((OUT / 'run-manifest.json').read_text())
sys.path.insert(0, manifest['runtime'])
from copilot.diagnostics import extraction as diagnostic_extraction
from copilot.diagnostics.facts import build_diagnostic_state
from copilot.qualification import facts


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = Path(manifest['baseline_runtime']) / 'copilot'
old_facts = load('copilot.qualification._fact_check_before', old / 'qualification/facts.py')
old_geo = load('copilot.pricing_tools._fact_check_before', old / 'pricing_tools/qualification.py')
expected = {**{f'GT-LBS-AC-{i:03}': {'details_sku': 'Place Details Essentials'} for i in range(21, 25)},
            'GT-LBS-RG-010': {'storage_required': True}, 'GT-LBS-RG-014': {'storage_required': True},
            'GT-LBS-DIR-050': {'traffic_required': True}, 'GT-LBS-RG-228': {'languages': 'Hindi'},
            'GT-LBS-RG-230': {'rooftop_hard_filter': True, 'address_elements_required': True},
            'GT-LBS-DM-034': {'usage_geography': 'India', 'traffic_scope': 'with_and_without'},
            'GT-LBS-DIR-049': {'max_stops': None}}


def main():
    packet = json.loads((OUT / 'review-cases.json').read_text())
    checks = []
    for case in packet:
        if case['record_id'] not in expected:
            continue
        enquiry = {'query': case['query'], 'history': case['history']}
        for method in ['baseline', 'integrated']:
            geo = old_geo.explicit_geographies if method == 'baseline' else diagnostic_extraction.explicit_geographies
            with patch.object(diagnostic_extraction, 'explicit_geographies', geo):
                state = build_diagnostic_state(enquiry)
                result = {'diagnostic_context': {'interpretation': {'api': 'directions', 'intent': 'sales_qualification'}},
                          'outputs': {'qualification_details': {}}}
                context = (old_facts if method == 'baseline' else facts).context_from_result(result, state, enquiry)
            for field, value in expected[case['record_id']].items():
                fact = context.facts.get(field)
                actual = fact.value if fact and fact.status == 'supplied' else None
                checks.append({'record_id': case['record_id'], 'method': method, 'field': field,
                               'expected': value, 'actual': actual, 'correct': actual == value,
                               'fact': fact.model_dump(mode='json') if fact else None})
    summary = {method: {'checks': sum(r['method'] == method for r in checks),
                        'correct': sum(r['method'] == method and r['correct'] for r in checks)}
               for method in ['baseline', 'integrated']}
    (OUT / 'targeted-fact-checks.json').write_text(json.dumps({'scope': '13 targeted supplied/unknown decisions in 11 working cases; not general extraction accuracy.',
        'summary': summary, 'checks': checks}, ensure_ascii=False, indent=2) + '\n')
    assert summary['integrated'] == {'checks': 13, 'correct': 13}
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
