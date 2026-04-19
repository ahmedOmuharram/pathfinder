"""Catalog per-1M-token price lookups for the Engine UI."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from genai_prices.data_snapshot import get_snapshot
from genai_prices.types import ModelPrice


@dataclass(frozen=True)
class PerMTokPrices:
    input_: float | None
    cached_input: float | None
    output: float | None


def _flatten_price(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    base = getattr(value, "base", None)
    if base is not None:
        return float(base)
    return None


def _resolve_active_model_price(raw: object) -> ModelPrice | None:
    if isinstance(raw, ModelPrice):
        return raw
    if isinstance(raw, list) and raw:
        last = raw[-1]
        price = getattr(last, "prices", None)
        if isinstance(price, ModelPrice):
            return price
    return None


def lookup_per_mtok_prices(provider: str, model: str) -> PerMTokPrices:
    """Headline $/1M-token for a ``(provider, model)`` pair; ``None`` when unknown."""
    snapshot = get_snapshot()
    for prov in snapshot.providers:
        if prov.id != provider:
            continue
        for mod in prov.models:
            if mod.id != model:
                continue
            active = _resolve_active_model_price(mod.prices)
            if active is None:
                return PerMTokPrices(input_=None, cached_input=None, output=None)
            return PerMTokPrices(
                input_=_flatten_price(active.input_mtok),
                cached_input=_flatten_price(active.cache_read_mtok),
                output=_flatten_price(active.output_mtok),
            )
    return PerMTokPrices(input_=None, cached_input=None, output=None)
