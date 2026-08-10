from __future__ import annotations

import re
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


# Database accessions: Pfam/PANTHER (PF00069), InterPro (IPR000023), GO
# (GO:0016301), EC (2.7.11.1). Distinctive enough that a token matching one in
# the vocabulary is a deliberate reference, not a coincidence.
# The trailing boundary is a lookahead, not ``\b``: an EC wildcard ends in a
# hyphen ("2.7.-.-"), and ``\b`` requires a word character before it, so the
# most common EC form in a request matched nothing at all.
_ACCESSION_RE = re.compile(
    r"\b(?:[A-Z]{2,}[:_]?\d{3,}|\d+(?:\.[\d-]+){2,})(?![0-9A-Za-z])",
    re.IGNORECASE,
)


def names_absent_accession(options: list[VocabOption], text: str) -> bool:
    """The text names an accession and the vocabulary has none of them.

    That is a contradiction, not an ambiguity: the user gave an exact
    identifier for a vocabulary that does not contain it -- typically because
    a dependent param narrowed it (asking for Pfam ``PF00069`` while
    ``domain_database`` is INTERPRO, whose 5,405 entries are all ``IPR``).

    Guessing here is how ``PF00069`` became ``IPR000023 :
    Phosphofructokinase_dom``. Returning True stops the chain so a Tier-3
    slot is opened and the model must pick a real value, fix the dependent
    param, or drop the criterion.
    """
    if not _ACCESSION_RE.search(text):
        return False
    return accession_in_text(options, text) is None


def sole_identifier_in_text(text: str) -> str | None:
    """The one database identifier the criterion names, if it names exactly one.

    For a param with NO vocabulary there is nothing to validate an identifier
    against, so the literal the user wrote is the value and WDK is what checks
    it. ``GenesByEcNumber.ec_wildcard`` is the case that exposed this: a visible
    required string whose declared default is the placeholder ``'N/A'``, so
    refusing the default is right -- and then the user was asked to confirm the
    ``2.7.-.-`` they had already written in the request.

    Two identifiers in one criterion is genuinely ambiguous and stays a
    question; guessing which one a param wants is how ``PF00069`` once became a
    phosphofructokinase domain.
    """
    tokens = {m.group(0) for m in _ACCESSION_RE.finditer(text)}
    return next(iter(tokens)) if len(tokens) == 1 else None


def accession_in_text(options: list[VocabOption], text: str) -> str | None:
    """A vocabulary entry whose value carries an accession named in the text.

    A user who writes "InterPro domain PF00069" has given an exact identifier.
    Semantic matching once bound `IPR000023 : Phosphofructokinase_dom` for that
    request -- the display text contains "kinase" -- and the strategy searched
    phosphofructokinase, returning 2 genes instead of 87 with verification
    reporting success.

    Only matches accessions that actually appear in the vocabulary. An
    identifier the vocabulary does not contain is handled by
    ``names_absent_accession`` rather than falling through, because the fuzzy
    tier is exactly what bound the wrong domain.
    """
    tokens = {m.group(0).casefold() for m in _ACCESSION_RE.finditer(text)}
    if not tokens:
        return None
    for option in options:
        value = option.value.casefold()
        for token in tokens:
            if value == token or value.startswith((f"{token} ", f"{token}:")):
                return option.value
    return None


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


_YES_NO = frozenset({"yes", "no"})


def _concept_from_param_name(name: str) -> str:
    """The thing a boolean param is asking about: ``isSyntenic`` -> "syntenic".

    WDK names these for the positive case, while a request is just as likely to
    be phrased as the negative ("non-syntenic orthologs"). The concept is what
    survives stripping the ``is``/``has`` prefix.
    """
    stem = re.sub(r"^(is|has)[_-]?", "", name, flags=re.IGNORECASE)
    return re.sub(r"[_-]+", " ", stem).strip().lower()


def _boolean_polarity(pi: ParameterInfo, text: str) -> str | None:
    """Resolve a yes/no vocabulary from how the criterion phrases the concept.

    ``None`` when the concept is not mentioned at all -- silence is not a
    choice, and the param's own default is the right answer there.
    """
    options = pi.allowed_values or []
    if {o.value.strip().lower() for o in options} != _YES_NO:
        return None
    concept = _concept_from_param_name(pi.name)
    if not concept:
        return None
    low = text.lower()
    if re.search(rf"\b(?:non|not)[\s-]*{re.escape(concept)}\b", low):
        return match_option(options, "no")
    if re.search(rf"\b{re.escape(concept)}\b", low):
        return match_option(options, "yes")
    return None


def _organism_value(pi: ParameterInfo, intent: ParamIntent) -> str | None:
    """An organism named in THIS criterion's text (e.g. an orthology target) is
    more specific than the strategy-wide anchor and wins over it."""
    opts = pi.allowed_values or []
    named = _named_in_text(opts, intent.text)
    if named is not None:
        return named
    scope = (intent.organism_scope or "").lower()
    for key, term in _ORG_TERMS:
        if key in scope:
            return match_option(opts, term) or term
    return None


def _direction_value(pi: ParameterInfo, intent: ParamIntent) -> str | None:
    """Match the FULL label before the bare token: "up" is a substring of "up or
    down regulated", so the token alone silently selects the both-directions
    option and drops the directional filter entirely."""
    want = intent.direction_hint or _direction_from_text(intent.text)
    if want is None:
        return None
    opts = pi.allowed_values or []
    label = "up-regulated" if want == "up" else "down-regulated"
    return match_option(opts, label) or match_option(opts, want)


def _rule_value(pi: ParameterInfo, intent: ParamIntent) -> str | None:
    low = pi.name.lower()
    if "organism" in low:
        return _organism_value(pi, intent)
    if contrast_role(pi) == "comparison":
        # The group named literally in the criterion text is the subject of the
        # contrast. A verbatim vocabulary term is much stronger evidence than a
        # similarity score -- real embeddings score both "male" and "female"
        # below the floor here, leaving the contrast unresolvable when the
        # answer is right there in the text.
        named = _named_in_text(pi.allowed_values or [], intent.text)
        if named is not None:
            return named
    polarity = _boolean_polarity(pi, intent.text)
    if polarity is not None:
        return polarity
    if is_direction_param(pi.name):
        return _direction_value(pi, intent)
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
    # `allowed_values` is capped at 50 entries, so an accession in a large
    # vocabulary is only visible in `vocab_leaves` (excluded from the
    # model-facing payload, kept for internal lookup like this).
    if not pi.allowed_values and not pi.vocab_leaves:
        # Nothing to match an identifier against, so the literal in the text is
        # the value itself and WDK is what validates it. Handled as its own
        # branch because ``names_absent_accession`` below is trivially true
        # without a vocabulary, and would turn every such param into a question
        # whose answer the user already wrote. The named rules still win: an
        # organism scope resolves without options at all.
        return _rule_value(pi, intent) or sole_identifier_in_text(intent.text)
    named = accession_in_text(
        [*(pi.allowed_values or []), *pi.vocab_leaves], intent.text
    )
    if named is not None:
        return named
    if names_absent_accession(
        [*(pi.allowed_values or []), *pi.vocab_leaves], intent.text
    ):
        return None
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
