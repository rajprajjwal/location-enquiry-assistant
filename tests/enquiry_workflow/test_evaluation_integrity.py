"""Reject ambiguous gold files instead of silently scoring their last duplicate."""
import json

import pytest

from copilot.diagnostics.evaluation import bind_review, score_bound_review


def write_case(tmp_path, labels):
    predictions = tmp_path / 'predictions.jsonl'
    gold = tmp_path / 'gold.json'
    predictions.write_text(json.dumps({
        'record_id': 'SYN-1', 'questions': {'candidate': ['What is the peak request rate?']},
    }) + '\n')
    gold.write_text(json.dumps({'cases': labels}))
    review = bind_review(predictions, gold, [{
        'record_id': 'SYN-1', 'methods': {'candidate': {'whole': [[1, 1]], 'facts': [[1, 1, 1]]}},
    }], reviewer='Synthetic integrity regression')
    return predictions, gold, review


@pytest.mark.parametrize('conflicting', [False, True])
def test_duplicate_gold_ids_fail_even_when_file_hashes_are_bound(tmp_path, conflicting):
    first = {'record_id': 'SYN-1', 'questions': [
        {'question': 'What is the peak request rate?', 'facts': ['The peak request rate.']},
    ]}
    second = {'record_id': 'SYN-1', 'questions': [
        {'question': 'Where will the service operate?', 'facts': ['The operating region.']},
    ]} if conflicting else first
    predictions, gold, review = write_case(tmp_path, [first, second])
    with pytest.raises(ValueError, match='Gold record IDs must be unique'):
        score_bound_review(predictions, gold, review)


def test_unique_bound_gold_keeps_the_existing_scores(tmp_path):
    label = {'record_id': 'SYN-1', 'questions': [
        {'question': 'What is the peak request rate?', 'facts': ['The peak request rate.']},
    ]}
    predictions, gold, review = write_case(tmp_path, [label])
    scores = score_bound_review(predictions, gold, review)['candidate']
    assert scores['f1'] == scores['precision'] == scores['recall'] == scores['fact_recall'] == 1
    assert scores['predicted'] == scores['gold'] == scores['matches'] == 1
