from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Literal

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.integrations.embeddings.prefixes import (
    SEARCH_DOCUMENT_PREFIX,
    SEARCH_QUERY_PREFIX,
)
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_formatting import ParameterInfo

EmbedFn = Callable[[Sequence[str]], Awaitable[list[list[float]]]]
_SEMANTIC_FLOOR = 0.45

_ORG_TERMS: list[tuple[str, str]] = [
    ("falciparum", "Plasmodium falciparum 3D7"),
    ("berghei", "Plasmodium berghei ANKA"),
    ("vivax", "Plasmodium vivax P01"),
    ("yoelii", "Plasmodium yoelii yoelii 17X"),
    ("knowlesi", "Plasmodium knowlesi strain H"),
]


class ParamIntent(CamelModel):
    organism_scope: str | None = None
    text: str = ""
    direction_hint: Literal["up", "down"] | None = None


def _direction_from_text(text: str) -> Literal["up", "down"] | None:
    low = text.lower()
    if any(
        k in low for k in ("downregulat", "down-regulat", "underexpress", "repress")
    ):
        return "down"
    if any(k in low for k in ("upregulat", "up-regulat", "overexpress", "induc")):
        return "up"
    return None


def match_option(options: list[VocabOption], hint: str) -> str | None:
    """Map a free-text hint to a vocab value: exact (value/display) first, then
    substring. Returns ``None`` when nothing matches."""
    h = hint.lower()
    for o in options:
        if h in (o.value.lower(), o.display.lower()):
            return o.value
    for o in options:
        if h in o.display.lower() or h in o.value.lower():
            return o.value
    return None


def _named_in_text(options: list[VocabOption], text: str) -> str | None:
    """A vocab value whose name appears verbatim in the criterion text — an
    intentional, specific per-criterion choice (e.g. the TARGET organism of an
    orthology search). Prefers the longest match so 'Toxoplasma gondii ME49'
    beats a bare 'Toxoplasma'. Vocab-driven — no per-search special-casing."""
    low = text.lower()
    named = [
        o.value for o in options if o.display.lower() in low or o.value.lower() in low
    ]
    return max(named, key=len) if named else None


def _rule_value(pi: ParameterInfo, intent: ParamIntent) -> str | None:
    low = pi.name.lower()
    opts = pi.allowed_values or []
    if "organism" in low:
        # An organism named in THIS criterion's text (e.g. an orthology target)
        # is more specific than the strategy-wide anchor and wins over it.
        named = _named_in_text(opts, intent.text)
        if named is not None:
            return named
        scope = (intent.organism_scope or "").lower()
        for key, term in _ORG_TERMS:
            if key in scope:
                return match_option(opts, term) or term
        return None
    if "regulated_dir" in low or low.endswith("_dir") or "direction" in low:
        want = intent.direction_hint or _direction_from_text(intent.text)
        if want is not None:
            label = "up-regulated" if want == "up" else "down-regulated"
            return match_option(opts, want) or match_option(opts, label)
    return None


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


async def _semantic_value(
    options: list[VocabOption], text: str, embed: EmbedFn
) -> str | None:
    if not options or not text.strip():
        return None
    texts = [SEARCH_QUERY_PREFIX + text]
    texts.extend(SEARCH_DOCUMENT_PREFIX + (o.display or o.value) for o in options)
    vectors = await embed(texts)
    query = vectors[0]
    best: str | None = None
    best_sim = _SEMANTIC_FLOOR
    for option, vector in zip(options, vectors[1:], strict=False):
        sim = _cosine(query, vector)
        if sim >= best_sim:
            best, best_sim = option.value, sim
    return best


async def map_intent_to_value(
    pi: ParameterInfo, intent: ParamIntent, *, embed: EmbedFn
) -> str | None:
    """Tier-2: map a criterion's intent to a valid vocab value (rules first,
    injected semantic match second). Returns ``None`` when genuinely
    ambiguous — the caller then opens a Tier-3 slot rather than guessing."""
    rule = _rule_value(pi, intent)
    if rule is not None:
        return rule
    return await _semantic_value(pi.allowed_values or [], intent.text, embed)
