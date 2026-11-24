"""Recorded model replies replay to the same predictions file."""

from __future__ import annotations

from copilot.enquiry_interpretation.run_batch import replay_batch, run_batch
from tests.support.helpers import ScriptedClient, completion, model_json


def test_replay_matches_the_recorded_predictions(tmp_path) -> None:
    records = [
        {"record_id": "SYN-1", "query": "What parameters does the API take?"},
        {
            "record_id": "SYN-2",
            "query": "What is the directions price?",
            "history": [{"role": "user", "text": "We operate in India."}],
        },
    ]
    client = ScriptedClient(
        [
            completion(model_json(), latency_ms=5),
            completion(
                model_json(
                    intent="pricing_quote",
                    sub_intent="pricing_quote",
                    api="directions",
                    team="Sales",
                ),
                latency_ms=9,
            ),
        ]
    )
    first = tmp_path / "live"
    second = tmp_path / "replay"
    run_batch(records, out_dir=first, client=client)
    replay_batch(records, first / "raw_responses.jsonl", second)
    assert (first / "predictions.jsonl").read_text(encoding="utf-8") == (
        second / "predictions.jsonl"
    ).read_text(encoding="utf-8")
    raw = (first / "raw_responses.jsonl").read_text(encoding="utf-8")
    assert "SYN-1" in raw and "SYN-2" in raw
    assert "prompt_tokens" in raw
