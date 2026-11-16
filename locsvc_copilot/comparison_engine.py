from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Dict, Iterable, List, Mapping, Optional

SUPPORTED_APIS = ("directions", "distance_matrix", "autocomplete", "reverse_geocode")
BILLING_UNIT_FACTORS = {
    "request": 1.0,
    "requests": 1.0,
    "call": 1.0,
    "calls": 1.0,
    "transaction": 1.0,
    "transactions": 1.0,
    "1k_requests": 1000.0,
    "1000_requests": 1000.0,
    "1k_calls": 1000.0,
    "1000_calls": 1000.0,
    "thousand_requests": 1000.0,
    "thousand_calls": 1000.0,
}


@dataclass(frozen=True)
class PriceTier:
    lower_bound: float = 0.0
    upper_bound: Optional[float] = None
    price_per_unit: float = 0.0
    currency: str = "USD"
    unit: str = "request"
    description: str = ""


@dataclass
class PricePlan:
    provider: str
    api: str
    currency: str = "USD"
    unit: str = "request"
    free_quota: float = 0.0
    pay_as_you_go_rate: Optional[float] = None
    tiers: List[PriceTier] = field(default_factory=list)
    source_url: str = ""
    retrieved_date: str = ""
    notes: List[str] = field(default_factory=list)

    def normalized_free_quota(self) -> float:
        return normalize_billing_unit(self.free_quota, self.unit)


@dataclass(frozen=True)
class CapabilityComparison:
    provider: str
    api: str
    capability: str
    status: str
    details: str = ""


@dataclass(frozen=True)
class CoverageStatus:
    provider: str
    region: str
    status: str
    notes: str = ""


@dataclass(frozen=True)
class LimitComparison:
    provider: str
    api: str
    metric: str
    value: str
    status: str = "verified"


def normalize_billing_unit(value: float, unit: str) -> float:
    """Normalize billing units into a consistent request-count basis."""
    if not isfinite(float(value)):
        raise ValueError(f"Billing value must be finite: {value!r}")
    if unit is None or unit == "":
        return float(value)
    key = str(unit).strip().lower().replace(" ", "_")
    if key not in BILLING_UNIT_FACTORS:
        raise ValueError(f"Unsupported billing unit: {unit!r}")
    return float(value) * BILLING_UNIT_FACTORS[key]


def _tiered_cost(plan: PricePlan, usage_after_free: float) -> float:
    if not plan.tiers:
        return 0.0

    total = 0.0
    tiers = sorted(plan.tiers, key=lambda t: t.lower_bound)
    for tier in tiers:
        start = max(tier.lower_bound, 0.0)
        end = tier.upper_bound if tier.upper_bound is not None else float("inf")
        if usage_after_free <= start:
            continue
        span = min(usage_after_free, end) - start
        if span > 0:
            total += span * tier.price_per_unit
    return total


def deterministic_cost_estimate(
    plan: PricePlan,
    monthly_usage: float,
    *,
    currency_rate: float = 1.0,
    monthly_usage_unit: str = "request",
) -> Optional[float]:
    """Deterministically estimate monthly cost for one provider and API."""
    if plan.api not in SUPPORTED_APIS:
        raise ValueError(f"Unsupported API for pricing: {plan.api!r}")

    usage_normalized = normalize_billing_unit(monthly_usage, monthly_usage_unit)
    quota = plan.normalized_free_quota()
    usage_after_free = max(usage_normalized - quota, 0.0)

    if usage_after_free <= 0:
        return 0.0

    total = 0.0
    if plan.tiers:
        total += _tiered_cost(plan, usage_after_free)
        remaining_after_tiers = usage_after_free - max(
            (tier.upper_bound if tier.upper_bound is not None else usage_after_free)
            for tier in plan.tiers
        )
        if remaining_after_tiers > 0 and plan.pay_as_you_go_rate is not None:
            total += remaining_after_tiers * plan.pay_as_you_go_rate
        elif remaining_after_tiers > 0 and plan.pay_as_you_go_rate is None:
            return None
    elif plan.pay_as_you_go_rate is not None:
        total += usage_after_free * plan.pay_as_you_go_rate
    else:
        return None

    return round(total * float(currency_rate), 4)


def compare_provider_pricing(
    api: str,
    monthly_usage: float,
    provider_plans: Mapping[str, PricePlan],
    *,
    region: str = "global",
    assumptions: Optional[Iterable[str]] = None,
    currency_rates: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """Return a deterministic comparison result for a set of provider plans."""
    if api not in SUPPORTED_APIS:
        raise ValueError(f"Unsupported API: {api!r}")

    rates = dict(currency_rates or {})
    result = {
        "comparison_id": f"cmp-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "requested_api": api,
        "providers": sorted(provider_plans.keys()),
        "geographic_region": region,
        "monthly_usage": monthly_usage,
        "pricing_details": {},
        "calculated_costs": {},
        "assumptions": list(assumptions or []),
        "missing_information": [],
        "source_references": [],
        "calculation_breakdown": {},
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    for provider, plan in sorted(provider_plans.items()):
        currency_rate = rates.get(plan.currency, 1.0)
        estimate = deterministic_cost_estimate(plan, monthly_usage, currency_rate=currency_rate)
        if estimate is None:
            result["missing_information"].append(f"Missing pricing data for {provider} on {api}")
        result["pricing_details"][provider] = {
            "api": plan.api,
            "currency": plan.currency,
            "unit": plan.unit,
            "free_quota": plan.free_quota,
            "pay_as_you_go_rate": plan.pay_as_you_go_rate,
            "tiers": [
                {
                    "lower_bound": tier.lower_bound,
                    "upper_bound": tier.upper_bound,
                    "price_per_unit": tier.price_per_unit,
                    "currency": tier.currency,
                    "unit": tier.unit,
                    "description": tier.description,
                }
                for tier in plan.tiers
            ],
            "source_url": plan.source_url,
            "retrieved_date": plan.retrieved_date,
            "notes": plan.notes,
        }
        result["calculated_costs"][provider] = estimate
        result["calculation_breakdown"][provider] = {
            "usage_normalized": normalize_billing_unit(monthly_usage, plan.unit),
            "free_quota_normalized": plan.normalized_free_quota(),
            "currency_rate": currency_rate,
            "estimated_cost": estimate,
        }
        if plan.source_url:
            result["source_references"].append({"provider": provider, "url": plan.source_url})

    return result


def compare_capabilities(
    api: str,
    capability_matrix: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> Dict[str, Any]:
    """Compare API capabilities across providers, distinguishing supported/unsupported/documented states."""
    if api not in SUPPORTED_APIS:
        raise ValueError(f"Unsupported API: {api!r}")

    results: Dict[str, Any] = {"requested_api": api, "providers": {}}
    for provider, provider_map in sorted(capability_matrix.items()):
        data = provider_map.get(api, {})
        provider_results: Dict[str, Any] = {}

        def capture_capability(capability_name: str, value: Any) -> None:
            status = "not_documented"
            detail = "Not documented in approved provider sources."
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"supported", "yes", "true"}:
                    status = "supported"
                    detail = "Documented as supported."
                elif normalized in {"not_supported", "no", "false"}:
                    status = "not_supported"
                    detail = "Documented as not supported."
                else:
                    status = "not_verified"
                    detail = str(value)
            elif isinstance(value, Mapping):
                status = str(value.get("status", "not_documented")).lower()
                detail = str(value.get("details", ""))
            provider_results[capability_name] = {"status": status, "details": detail}

        for capability_name, value in data.items():
            if isinstance(value, Mapping) and "status" in value:
                capture_capability(capability_name, value)
            else:
                capture_capability(capability_name, value)

        results["providers"][provider] = provider_results
    return results


def compare_coverage(
    api: str,
    coverage_map: Mapping[str, Mapping[str, str]],
    region: str,
) -> Dict[str, Any]:
    """Return provider-level coverage for the requested region."""
    if api not in SUPPORTED_APIS:
        raise ValueError(f"Unsupported API: {api!r}")

    response = {"requested_api": api, "region": region, "providers": {}}
    for provider, provider_inputs in sorted(coverage_map.items()):
        provider_status = provider_inputs.get(region, "not_documented")
        response["providers"][provider] = {
            "status": provider_status,
            "notes": provider_inputs.get(f"{region}_notes", "No region-specific notes provided."),
        }
    return response


def compare_limits(
    api: str,
    limits_map: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    """Return limit and quota comparisons for each provider."""
    if api not in SUPPORTED_APIS:
        raise ValueError(f"Unsupported API: {api!r}")

    return {"requested_api": api, "providers": {provider: data for provider, data in sorted(limits_map.items())}}
