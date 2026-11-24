"""Verify and reproduce the saved final working-eval question score."""
from hashlib import sha256
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[4]
sys.path.insert(0, str(REPO))
from copilot.diagnostics.evaluation import score_bound_review

review = json.loads((OUT/'candidate-v3-bound-review.json').read_text())
full = OUT/'candidate-v3/predictions.jsonl'
assert sha256(full.read_bytes()).hexdigest() == review['source_full_predictions_sha256']
score = score_bound_review(OUT/'candidate-v3-score-predictions.jsonl',
                           OUT/'original-working-reference.json', review)['candidate-v3']
expected = json.loads((OUT/'candidate-v3-score.json').read_text())['overall']
assert score == expected
print(json.dumps(score, indent=2))
