"""Reproduce frozen scores from immutable saved predictions and semantic review."""
import json
from pathlib import Path
import sys

if __name__ == '__main__':
    folder = Path(__file__).resolve().parent
    sys.path.insert(0, str(folder / 'runtime'))
    from copilot.diagnostics.evaluation import score_bound_review
    review = json.loads((folder / 'question-review.bound.json').read_text())
    print(json.dumps(score_bound_review(folder / 'predictions.jsonl', folder / 'locked-gold.json', review), indent=2))
