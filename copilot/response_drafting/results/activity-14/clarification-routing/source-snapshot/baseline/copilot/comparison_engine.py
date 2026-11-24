# Source history: Vinayagam Raja (ca2437d), master. See copilot/enquiry_workflow/source-history.json.
from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
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
    """Billable request-count bounds and a rate in the tier's billing unit."""

    lower_bound: float = 0.0
    upper_bound: Optional[float] = None
    price_per_unit: float = 0.0
    currency: str = "USD"
    unit: str = "request"
    description: str = ""


@dataclass
class PricePlan:
    """Use the plan billing unit for the free quota and flat or overflow rate."""

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


def _number(value: float) -> Decimal:
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Billing value must be numeric: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"Billing value must be finite: {value!r}")
    return number


def _unit_factor(unit: str) -> Decimal:
    if unit is None or unit == "":
        return Decimal(1)
    key = str(unit).strip().lower().replace(" ", "_")
    try:
        return Decimal(BILLING_UNIT_FACTORS[key])
    except KeyError:
        raise ValueError(f"Unsupported billing unit: {unit!r}") from None


def normalize_billing_unit(value: float, unit: str) -> float:
    """Normalize billing units into a consistent request-count basis."""
    return float(_number(value) * _unit_factor(unit))


def _rate_per_request(rate: float, unit: str) -> Decimal:
    return _number(rate) / _unit_factor(unit)


def _tiered_cost(plan: PricePlan, usage: Decimal) -> Optional[Decimal]:
    total = Decimal(0)
    billed = Decimal(0)
    for tier in sorted(plan.tiers, key=lambda item: item.lower_bound):
        start = max(_number(tier.lower_bound), Decimal(0))
        if start >= usage:
            break
        end = usage if tier.upper_bound is None else min(usage, _number(tier.upper_bound))
        # Uncovered or overlapping billable ranges cannot yield an unambiguous estimate.
        if end <= start or start != billed:
            return None
        total += (end - start) * _rate_per_request(tier.price_per_unit, tier.unit)
        billed = end

    if billed == usage:
        return total
    if plan.pay_as_you_go_rate is None:
        return None
    return total + (usage - billed) * _rate_per_request(plan.pay_as_you_go_rate, plan.unit)


def deterministic_cost_estimate(
    plan: PricePlan,
    monthly_usage: float,
    *,
    currency_rate: float = 1.0,
    monthly_usage_unit: str = "request",
) -> Optional[float]:
    """Estimate monthly cost, prorating rates per billing unit by request count."""
    if plan.api not in SUPPORTED_APIS:
        raise ValueError(f"Unsupported API for pricing: {plan.api!r}")

    usage = _number(monthly_usage) * _unit_factor(monthly_usage_unit)
    quota = _number(plan.free_quota) * _unit_factor(plan.unit)
    billable = max(usage - quota, Decimal(0))
    if not billable:
        return 0.0

    total = _tiered_cost(plan, billable)
    return float(round(total * _number(currency_rate), 4)) if total is not None else None


def compare_provider_pricing(
    api: str,
    monthly_usage: float,
    provider_plans: Mapping[str, PricePlan],
    *,
    region: str = "global",
    assumptions: Optional[Iterable[str]] = None,
    currency_rates: Optional[Mapping[str, float]] = None,
    monthly_usage_unit: str = "request",
    execution_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare a common workload. Supply a timestamp when recording execution metadata."""
    if api not in SUPPORTED_APIS:
        raise ValueError(f"Unsupported API: {api!r}")

    rates = dict(currency_rates or {})
    usage_normalized = normalize_billing_unit(monthly_usage, monthly_usage_unit)
    ordered_assumptions = sorted(assumptions) if isinstance(assumptions, Set) else list(assumptions or [])
    result = {
        "requested_api": api,
        "providers": sorted(provider_plans.keys()),
        "geographic_region": region,
        "monthly_usage": monthly_usage,
        "monthly_usage_unit": monthly_usage_unit,
        "pricing_details": {},
        "calculated_costs": {},
        "assumptions": ordered_assumptions,
        "missing_information": [],
        "source_references": [],
        "calculation_breakdown": {},
    }

    for provider, plan in sorted(provider_plans.items()):
        currency_rate = rates.get(plan.currency, 1.0)
        estimate = deterministic_cost_estimate(
            plan, monthly_usage, currency_rate=currency_rate, monthly_usage_unit=monthly_usage_unit,
        )
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
                for tier in sorted(plan.tiers, key=lambda item: item.lower_bound)
            ],
            "source_url": plan.source_url,
            "retrieved_date": plan.retrieved_date,
            "notes": plan.notes,
        }
        result["calculated_costs"][provider] = estimate
        result["calculation_breakdown"][provider] = {
            "usage_normalized": usage_normalized,
            "free_quota_normalized": plan.normalized_free_quota(),
            "currency_rate": currency_rate,
            "estimated_cost": estimate,
        }
        if plan.source_url:
            result["source_references"].append({"provider": provider, "url": plan.source_url})

    # The comparison identity depends on its content. Timestamp metadata is caller-supplied.
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    result["comparison_id"] = f"cmp-{sha256(payload.encode('utf-8')).hexdigest()[:24]}"
    result["execution_timestamp"] = execution_timestamp
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
