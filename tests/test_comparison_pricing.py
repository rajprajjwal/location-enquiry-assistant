import json

import pytest

from copilot.comparison_engine import (
    PricePlan,
    PriceTier,
    compare_provider_pricing,
    deterministic_cost_estimate,
)


@pytest.mark.parametrize(("plan_unit", "rate", "quota", "usage", "usage_unit", "fx", "expected"), [
    ("request", 0.02, 0, 5000, "request", 1, 100),
    ("request", 0.02, 1000, 5000, "request", 1, 80),
    ("request", 0.003, 50, 100, "request", 1, 0.15),
    ("request", 0.25, 2, 1, "request", 1, 0),
    ("request", 0.25, 2, 2, "request", 1, 0),
    ("request", 0.25, 2, 3, "request", 1, 0.25),
    ("1k_requests", 2, 0, 5000, "request", 1, 10),
    ("1k_requests", 2, 0, 350, "request", 1, 0.7),
    ("1k_requests", 2, 1, 5000, "request", 1, 8),
    ("1k_requests", 2, 0.5, 2.5, "1k_requests", 1, 4),
    ("1k_requests", 2, 0.5, 500, "request", 1, 0),
    ("thousand calls", 2, 0.5, 750, "calls", 1, 0.5),
    ("transaction", 0.5, 0, 2, "1000_calls", 1, 1000),
    ("1000_calls", 4, 0.25, 500, "calls", 2.5, 2.5),
    ("1k_requests", 0, 0, 4000, "request", 1, 0),
    ("request", 0.02, 0, 0, "request", 1, 0),
])
def test_flat_billing_matches_hand_calculated_cost(plan_unit, rate, quota, usage, usage_unit, fx, expected):
    plan = PricePlan("Example", "directions", unit=plan_unit, free_quota=quota, pay_as_you_go_rate=rate)
    assert deterministic_cost_estimate(plan, usage, monthly_usage_unit=usage_unit, currency_rate=fx) == expected


@pytest.mark.parametrize(("usage", "unit", "fx", "expected"), [
    (0, "request", 1, 0),
    (499, "request", 1, 0),
    (500, "request", 1, 0),
    (501, "request", 1, 0.002),
    (1000, "request", 1, 1),
    (1499, "request", 1, 1.998),
    (1500, "request", 1, 2),
    (1501, "request", 1, 2.0015),
    (2500, "request", 1, 3.5),
    (3499, "request", 1, 4.9985),
    (3500, "request", 1, 5),
    (3501, "request", 1, 5.001),
    (3550, "request", 1, 5.05),
    (4500, "request", 1, 6),
    (4.5, "1k_requests", 1, 6),
    (4.5, "1k_calls", 2.25, 13.5),
])
def test_tiered_billing_matches_hand_calculated_cost(usage, unit, fx, expected):
    # First 500 requests free, next 1,000 cost 2, next 2,000 cost 3, and overflow costs 1 per 1,000.
    plan = PricePlan(
        "Example", "distance_matrix", unit="1k_requests", free_quota=0.5, pay_as_you_go_rate=1,
        tiers=[PriceTier(1000, 3000, 0.0015), PriceTier(0, 1000, 2, unit="1k_requests")],
    )
    assert deterministic_cost_estimate(plan, usage, monthly_usage_unit=unit, currency_rate=fx) == expected


def test_open_ended_tier_uses_its_own_unit():
    plan = PricePlan(
        "Example", "autocomplete", unit="1k_calls", pay_as_you_go_rate=9,
        tiers=[PriceTier(0, 1000, 0.01), PriceTier(1000, None, 0.5, unit="1k_requests")],
    )
    assert deterministic_cost_estimate(plan, 5000) == 12


@pytest.mark.parametrize("tiers", [
    [],
    [PriceTier(0, 1000, 2, unit="1k_requests")],
    [PriceTier(0, 1000, 0.01), PriceTier(2000, None, 0.02)],
    [PriceTier(0, 2500, 0.01), PriceTier(2000, None, 0.02)],
])
def test_unpriced_or_ambiguous_ranges_do_not_produce_a_cost(tiers):
    plan = PricePlan("Example", "autocomplete", tiers=tiers)
    assert deterministic_cost_estimate(plan, 3000) is None


def test_pricing_output_is_byte_identical_and_reports_the_same_workload():
    a = PricePlan("Alpha", "directions", unit="1k_requests", pay_as_you_go_rate=2,
                  source_url="https://example.com/alpha")
    b = PricePlan("Beta", "directions", pay_as_you_go_rate=0.004, source_url="https://example.com/beta")
    kwargs = {"assumptions": {"Same API", "Same workload"}, "monthly_usage_unit": "1k_requests"}
    first = compare_provider_pricing("directions", 5, {"Alpha": a, "Beta": b}, **kwargs)
    second = compare_provider_pricing("directions", 5, {"Beta": b, "Alpha": a}, **kwargs)

    assert json.dumps(first).encode() == json.dumps(second).encode()
    assert first["comparison_id"].startswith("cmp-")
    assert first["execution_timestamp"] is None
    assert first["monthly_usage_unit"] == "1k_requests"
    assert first["calculated_costs"] == {"Alpha": 10, "Beta": 20}
    assert {item["usage_normalized"] for item in first["calculation_breakdown"].values()} == {5000}
    assert first["assumptions"] == ["Same API", "Same workload"]
    assert first["source_references"] == [
        {"provider": "Alpha", "url": "https://example.com/alpha"},
        {"provider": "Beta", "url": "https://example.com/beta"},
    ]
    assert first["comparison_id"] != compare_provider_pricing("directions", 6, {"Alpha": a, "Beta": b}, **kwargs)["comparison_id"]


def test_explicit_timestamp_is_reproducible_and_kept_as_metadata():
    plan = PricePlan("Example", "directions", pay_as_you_go_rate=1.5)
    args = ("directions", 4, {"Example": plan})
    timestamp = "2026-11-22T12:00:00+00:00"
    first = compare_provider_pricing(*args, execution_timestamp=timestamp)
    second = compare_provider_pricing(*args, execution_timestamp=timestamp)
    assert json.dumps(first).encode() == json.dumps(second).encode()
    assert first["execution_timestamp"] == timestamp
    assert compare_provider_pricing(*args)["comparison_id"] == first["comparison_id"]
