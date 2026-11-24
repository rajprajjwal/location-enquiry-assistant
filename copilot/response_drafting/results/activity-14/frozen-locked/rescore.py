"""Reproduce frozen question scores from saved predictions and bound review."""
import json
from pathlib import Path
from copilot.diagnostics.evaluation import score_bound_review

if __name__ == '__main__':
    folder = Path(__file__).resolve().parent
    review = json.loads((folder / 'question-review.bound.json').read_text())
    print(json.dumps(score_bound_review(folder / 'predictions.jsonl', folder / 'locked-gold.json', review), indent=2))
