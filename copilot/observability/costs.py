"""Price endpoint-reported usage without treating unknown prices as free."""
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal
import os

from pydantic import BaseModel, ConfigDict, Field
import yaml

from copilot.paths import CONFIG_DIR


class Rates(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    input_usd_per_million: Decimal | None = Field(default=None, ge=0)
    output_usd_per_million: Decimal | None = Field(default=None, ge=0)
    embedding_usd_per_million: Decimal | None = Field(default=None, ge=0)
    usd_to_inr: Decimal = Field(default=Decimal("94"), gt=0)
    cost_basis: Literal["configured", "illustrative"] = "configured"
    endpoint_access_free: bool = False
    source: str = "Unconfigured"


@lru_cache(maxsize=1)
def configured_rates():
    path = Path(os.environ.get("COPILOT_TRACE_RATES_FILE", CONFIG_DIR / "observability.yaml"))
    return Rates.model_validate(yaml.safe_load(path.read_text()) or {})


def aggregate_usage(spans, rates=None):
    if rates is None:
        try:
            rates = configured_rates()
        except Exception:
            rates = Rates(source="Invalid pricing configuration")
    input_tokens = output_tokens = embedding_tokens = missing_usage = 0
    attempts = []
    subtotal = Decimal(0)
    unpriced = False
    incomplete = False
    for span in spans:
        attrs = span["attributes"]
        kind = attrs.get("copilot.span.kind")
        if kind not in {"llm_attempt", "embedding_attempt"}:
            continue
        attempts.append(span)
        incoming = attrs.get("gen_ai.usage.input_tokens")
        outgoing = attrs.get("gen_ai.usage.output_tokens") if kind == "llm_attempt" else 0
        valid = all(type(v) is int and v >= 0 for v in (incoming, outgoing))
        if valid:
            if kind == "llm_attempt":
                input_tokens += incoming
                output_tokens += outgoing
            else:
                embedding_tokens += incoming
        else:
            missing_usage += 1
        prices = ((rates.input_usd_per_million, rates.output_usd_per_million)
                  if kind == "llm_attempt" else (rates.embedding_usd_per_million, Decimal(0)))
        if any(price is None for price in prices):
            unpriced = True
        elif all(price == 0 for price in prices):
            continue
        elif not valid:
            incomplete = True
        else:
            subtotal += (Decimal(incoming) * prices[0] + Decimal(outgoing) * prices[1]) / Decimal(1_000_000)
    status = "unpriced" if unpriced else "incomplete_usage" if incomplete else "complete"
    return {
        "model_attempts": sum(s["attributes"]["copilot.span.kind"] == "llm_attempt" for s in attempts),
        "embedding_attempts": sum(s["attributes"]["copilot.span.kind"] == "embedding_attempt" for s in attempts),
        "input_tokens": input_tokens, "output_tokens": output_tokens, "embedding_tokens": embedding_tokens,
        "missing_usage_attempts": missing_usage, "usage_complete": missing_usage == 0,
        "cost_usd": str(subtotal) if status == "complete" else None,
        "known_cost_usd": str(subtotal), "cost_status": status, "rate_source": rates.source,
        "cost_inr": str(subtotal * rates.usd_to_inr) if status == "complete" else None,
        "known_cost_inr": str(subtotal * rates.usd_to_inr), "usd_to_inr": str(rates.usd_to_inr), "currency": "INR",
        "cost_basis": rates.cost_basis,
        "actual_endpoint_charge_inr": "0" if rates.endpoint_access_free else None,
        "actual_endpoint_charge_usd": "0" if rates.endpoint_access_free else None,
    }
