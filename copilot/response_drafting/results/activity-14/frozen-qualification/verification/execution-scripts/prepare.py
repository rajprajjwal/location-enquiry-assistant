"""Lock the validated implementation and exact prior frozen cohort without relabeling."""
import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
OUT = ROOT / 'outputs/activity14-frozen-qualification'
RUNTIME = ROOT / 'work/activity14-frozen-qualification/runtime'
PRIOR = REPO / 'copilot/response_drafting/results/activity-14/frozen-locked'
WORKING = REPO / 'copilot/response_drafting/results/activity-14/clarification-routing'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def tagged(name):
    return subprocess.check_output(['git', 'show', 'eval-freeze-v4:eval/frozen-interpretation/' + name], cwd=REPO)


def main():
    previous = json.loads((PRIOR / 'run-manifest.json').read_text())
    validated = json.loads((WORKING / 'run-manifest.json').read_text())
    assert all(digest(REPO / p) == h for p, h in validated['code_hashes'].items())
    assert digest(REPO / 'data/ground-truth.xlsx') == previous['workbook_before_sha256']
    raw = tagged('inputs.jsonl')
    original = json.loads(tagged('manifest.json'))
    assert sha256(raw).hexdigest() == original['inputs_sha256'] == previous['frozen_inputs_sha256']
    inputs = [json.loads(line) for line in raw.splitlines()]
    ids = [r['record_id'] for r in inputs]
    assert ids == original['frozen_record_ids'] and len(ids) == len(set(ids)) == 80
    blob = tagged('ground-truth-frozen.csv')
    assert sha256(blob).hexdigest() == original['frozen_export']['sha256'] == previous['frozen_gt_sha256']
    records = list(csv.DictReader(StringIO(blob.decode('utf-8-sig'))))
    assert {r['id'] for r in records} == set(ids)
    assert all(r['split'] == 'eval' and r['frozen_core'].lower() in {'true', 'yes', '1'} for r in records)

    RUNTIME.mkdir(exist_ok=False)
    # Copy code and model/retrieval assets; production case stores and eval data are excluded.
    for path in (REPO / 'copilot').rglob('*'):
        rel = path.relative_to(REPO)
        parts = path.relative_to(REPO / 'copilot').parts
        if not path.is_file() or '__pycache__' in parts or 'results' in parts:
            continue
        if path.suffix == '.py' or (parts[:2] == ('model_gateway', 'assets')) or parts[0] == 'config':
            dest = RUNTIME / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
    processed = REPO / 'copilot/rag/data/processed'
    shutil.copytree(processed, RUNTIME / 'copilot/rag/data/processed')
    for folder in ['schemas', 'contracts', 'vocab', 'spec', 'mapping']:
        for path in (REPO / folder).rglob('*'):
            if path.is_file() and path.suffix in {'.py', '.json', '.txt', '.yaml', '.yml'} and '__pycache__' not in path.parts:
                if path.name.startswith('gold_outputs'):
                    continue
                dest = RUNTIME / path.relative_to(REPO)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
    # Interpretation prompts and keyword menus are runtime inputs too.
    for path in (REPO / 'copilot/enquiry_interpretation').rglob('*'):
        if path.is_file() and path.suffix in {'.json', '.txt'}:
            dest = RUNTIME / path.relative_to(REPO)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
    for name in ['requirements.txt', 'pyproject.toml']:
        shutil.copy2(REPO / name, RUNTIME / name)
    for name in ['review-cases.json', 'frozen-questions.json', 'locked-gold.json']:
        shutil.copy2(PRIOR / name, OUT / name)
    packet = json.loads((OUT / 'review-cases.json').read_text())
    gold = json.loads((OUT / 'locked-gold.json').read_text())
    assert [r['record_id'] for r in packet] == ids
    assert len(gold['cases']) == 80 and sum(len(r['questions']) for r in gold['cases']) == 75
    assert sum(len(q['facts']) for r in gold['cases'] for q in r['questions']) == 99
    assert digest(OUT / 'locked-gold.json') == previous['gold_sha256']
    assert digest(OUT / 'frozen-questions.json') == previous['official_questions_sha256']
    (OUT / 'inputs.jsonl').write_bytes(raw)
    (OUT / 'ground-truth-frozen.csv').write_bytes(blob)
    (OUT / 'frozen-input-manifest.json').write_bytes(tagged('manifest.json'))
    manifest = {
        'status': 'code_and_data_locked_before_frozen_predictions',
        'cases': 80, 'frozen_cases': 80, 'holdout_cases': 0,
        'runtime': str(RUNTIME), 'retrieval': {'mode': 'bm25', 'rerank': False},
        'model': 'Qwen/Qwen3-8B', 'few_shot_interpretation': False,
        'source_hashes': {str(p.relative_to(RUNTIME)): digest(p) for p in sorted(RUNTIME.rglob('*')) if p.is_file()},
        'code_hashes': {str(p.relative_to(RUNTIME)): digest(p) for p in (RUNTIME / 'copilot').rglob('*.py')},
        'frozen_inputs_sha256': sha256(raw).hexdigest(), 'frozen_gt_sha256': sha256(blob).hexdigest(),
        'gold_sha256': digest(OUT / 'locked-gold.json'), 'case_sha256': digest(OUT / 'review-cases.json'),
        'official_questions_sha256': digest(OUT / 'frozen-questions.json'),
        'workbook_before_sha256': digest(REPO / 'data/ground-truth.xlsx'),
        'prior_predictions_sha256': digest(PRIOR / 'predictions.jsonl'),
        'prior_score_sha256': digest(PRIOR / 'scores.json'),
        'prior_run_manifest_sha256': digest(PRIOR / 'run-manifest.json'),
        'working_validation_manifest_sha256': digest(WORKING / 'run-manifest.json'),
        'working_validation_scores_sha256': digest(WORKING / 'scores.json'),
        'working_tests': '559 tests and 4 subtests passed; code matches validated source hashes.',
        'frozen_record_ids': ids,
        'comparison': 'Historical prior frozen-locked integrated outputs. New run uses fresh endpoint requests; differences are observed, not isolated causal attribution.',
        'question_f1_threshold': 0.80,
        'evaluation_policy': 'Same 75 frozen questions and 99 prior derived facts, no relabeling, exclusions or application tuning during this run.',
    }
    write(OUT / 'implementation-lock.json', manifest)
    print(json.dumps({'locked': True, 'frozen_cases': 80, 'gold_questions': 75, 'gold_facts': 99,
                      'holdout_cases': 0, 'code_files': len(manifest['code_hashes']),
                      'runtime_files': len(manifest['source_hashes'])}))


if __name__ == '__main__':
    main()
