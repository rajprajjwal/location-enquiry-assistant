"""Score identical saved outputs against original and separately reviewed working references."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/fact-binding-working'
manifest = json.loads((OUT / 'run-manifest.json').read_text())
sys.path.insert(0, manifest['runtime'])
import copilot

spec = importlib.util.spec_from_file_location('binding_scorer', ROOT / 'work/qualification-validation/rescore_saved.py')
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def main():
    rows = [json.loads(line) for line in (OUT / 'predictions.jsonl').read_text().splitlines()]
    assert len(rows) == len({r['record_id'] for r in rows}) == 36
    results = {}
    for name, labels_path in [('original-reference', OUT / 'locked-gold.json'),
                              ('reviewed-reference', OUT / 'reviewed-reference.json')]:
        folder = OUT / name
        folder.mkdir(exist_ok=True)
        shutil.copy2(labels_path, folder / 'locked-gold.json')
        labels = {r['record_id']: r['questions'] for r in json.loads(labels_path.read_text())['cases']}
        adapted = [{**row, 'gold': labels[row['record_id']]} for row in rows]
        (folder / 'predictions.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in adapted))
        results[name] = scorer.score(folder)
        shutil.copy2(ROOT / 'work/qualification-validation/rescore_saved.py', folder / 'rescore.py')
    (OUT / 'scores.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
