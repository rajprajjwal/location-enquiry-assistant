"""Rules read user turns only."""

from __future__ import annotations

from copilot.interpret.rules import extract


def test_assistant_turns_are_not_mined() -> None:
    found = extract(
        history=[
            {
                "role": "assistant",
                "text": "Use the distance matrix in India by Q3 2026 with Google.",
            }
        ],
        query="hello",
    )
    assert found["unique_api"] is None
    assert found["user_turns"][-1]["region"] is None
    assert found["user_turns"][-1]["timeline"] is None
    assert found["user_turns"][-1]["current_provider"] is None


def test_user_turn_extracts_volume_region_and_api() -> None:
    found = extract(
        history=[],
        query="We need 20,000 directions requests a month in India.",
    )
    assert found["unique_api"] == "directions"
    turn = found["user_turns"][-1]
    assert turn["region"]["value"] == "India"
    assert turn["monthly_volume"]["value"]["requests_per_month"] == 20000
