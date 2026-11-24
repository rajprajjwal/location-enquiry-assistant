"""Retrieve pinned vendor pricing passages by calculator SKU."""
from copilot.paths import CONFIG_DIR
from functools import lru_cache
import json

from .pricing_calc import load_pricing

_FIELDS = ("tiers", "per", "currency", "unit", "beyond")


@lru_cache(maxsize=1)
def _evidence_index():
    path = CONFIG_DIR / "pricing-evidence.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _source_hit(identity, evidence):
    return {
        "document_id": identity,
        "source_url": evidence["url"],
        "relevant_passage": evidence["span"],
    }


def lookup(sku_id, *, include_fx=None):
    """Return evidence for the exact commercial SKU and calculator rate snapshot."""
    pricing = load_pricing()
    sku = pricing["skus"][sku_id]
    card = _evidence_index()["offers"].get(sku_id)
    if not card or any(card.get(field) != sku.get(field) for field in _FIELDS):
        return None
    if card["url"] not in pricing["sources"].get(sku["provider"], []):
        return None
    hits = [_source_hit(f"pricing:{sku_id}", card)]
    if include_fx is None:
        include_fx = sku["currency"] == "USD"
    if include_fx:
        fx = pricing["fx"]
        exchange = _evidence_index()["exchange_rate"]
        if (exchange["as_of"], exchange["usd_inr"]) != (str(fx["as_of"]), fx["usd_inr"]):
            return None
        hits.append(_source_hit(f"pricing:fx:{exchange['as_of']}", exchange))
    return hits
