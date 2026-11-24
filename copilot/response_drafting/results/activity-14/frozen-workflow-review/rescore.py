"""Reproduce the saved frozen score without model access."""
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT / 'runtime'))
from copilot.diagnostics.evaluation import score_bound_review

if __name__ == '__main__':
    review = json.loads((OUT / 'question-review.bound.json').read_text())
    score = score_bound_review(OUT / 'predictions.jsonl', OUT / 'locked-gold.json', review)
    assert score == json.loads((OUT / 'scores.json').read_text())
    print(json.dumps(score, indent=2))
