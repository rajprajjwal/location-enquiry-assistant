"""Reproduce saved question metrics from the prediction-bound semantic review."""
import json
from pathlib import Path
from copilot.diagnostics.evaluation import score_bound_review

if __name__ == '__main__':
    folder=Path(__file__).resolve().parent
    print(json.dumps(score_bound_review(folder/'predictions.jsonl',folder/'locked-gold.json',
        json.loads((folder/'question-review.bound.json').read_text())),indent=2))
