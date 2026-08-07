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


_REFERENCE_MARKERS = ("_ref_", "_ref", "reference")
_COMPARISON_MARKERS = ("_comp_", "_comp", "comparison", "comparator")


# A contrast is between SAMPLE GROUPS. WDK also names an "operation" pair with
# the same ref/comp markers (``min_max_avg_ref`` / ``_comp``: mean, median, min,
# max applied to each side) -- there, both sides taking "average" is normal and
# correct, so those must not be treated as a contrast at all.
_CONTRAST_SUBJECT_MARKERS = ("sample", "group")
# ...but WDK labels the operation pair "Operation Applied to Reference Samples",
# which mentions samples without selecting any. Exclude aggregation selectors
# explicitly: choosing "average" for both sides of a contrast is correct.
_AGGREGATION_MARKERS = ("operation", "min_max_avg")


def is_aggregation_param(name: str) -> bool:
    """Whether a param selects HOW to aggregate a side (mean/median/min/max)
    rather than WHICH samples that side contains. Both sides of a contrast
    legitimately use the same operation, so the degenerate-pair rule -- which
    exists to stop a group being compared against itself -- must not apply."""
    return any(m in name.lower() for m in _AGGREGATION_MARKERS)


def contrast_role_of(name: str) -> Literal["reference", "comparison"] | None:
    """Contrast role from a param name/label alone (no ``ParameterInfo``), for
    callers that only hold resolved param names -- e.g. the ledger view."""
    haystack = name.lower()
    if any(m in haystack for m in _AGGREGATION_MARKERS):
        return None
    if not any(m in haystack for m in _CONTRAST_SUBJECT_MARKERS):
        return None
    if any(m in haystack for m in _COMPARISON_MARKERS):
        return "comparison"
    if any(m in haystack for m in _REFERENCE_MARKERS):
        return "reference"
    return None


def is_direction_param(name: str) -> bool:
    low = name.lower()
    return "regulated_dir" in low or low.endswith("_dir") or "direction" in low


_ROLE_SLOT = "\x00"


def contrast_pair_key(name: str) -> str:
    """A key shared by the two halves of ONE contrast pair.

    ``samples_fc_comp_generic`` and ``samples_fc_ref_generic`` both reduce to
    ``samples_fc_\x00_generic``; ``min_max_avg_comp``/``_ref`` reduce to their
    own stem. Pairing on the stem keeps unrelated pairs independent, which a
    bare role match does not -- and unlike a vocabulary signature it survives a
    dependent param still carrying its pre-parent option set.
    """
    low = name.lower()
    for marker in (*_COMPARISON_MARKERS, *_REFERENCE_MARKERS):
        if marker in low:
            return low.replace(marker, _ROLE_SLOT, 1)
    return low


def contrast_role(pi: ParameterInfo) -> Literal["reference", "comparison"] | None:
    """Which side of a differential contrast this sample selector fills.

    WDK computes fold change as comparator-vs-reference, so the two are NOT
    interchangeable: the group the user wants enriched belongs in the
    comparator, and the baseline in the reference. Read from the param name and
    its display label ("Reference Samples" / "Comparison Samples"), both of
    which WDK supplies consistently across the DESeq and fold-change families.
    """
    return contrast_role_of(f"{pi.name} {pi.display_name}")


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
    if contrast_role(pi) == "comparison":
        # The group named literally in the criterion text is the subject of the
        # contrast. A verbatim vocabulary term is much stronger evidence than a
        # similarity score -- real embeddings score both "male" and "female"
        # below the floor here, leaving the contrast unresolvable when the
        # answer is right there in the text.
        named = _named_in_text(opts, intent.text)
        if named is not None:
            return named
    if "regulated_dir" in low or low.endswith("_dir") or "direction" in low:
        want = intent.direction_hint or _direction_from_text(intent.text)
        if want is not None:
            # Match the FULL label before the bare token: "up" is a substring of
            # "up or down regulated", so the token alone silently selects the
            # both-directions option and drops the directional filter entirely.
            label = "up-regulated" if want == "up" else "down-regulated"
            return match_option(opts, label) or match_option(opts, want)
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
    if contrast_role(pi) == "reference":
        # The criterion text names what the user wants ENRICHED, which is the
        # comparator. Semantic-matching it into the reference slot inverts the
        # contrast. Leave the baseline to be deduced from the remaining option
        # (or asked about) once the comparator has taken the subject.
        return None
    return await _semantic_value(pi.allowed_values or [], intent.text, embed)
