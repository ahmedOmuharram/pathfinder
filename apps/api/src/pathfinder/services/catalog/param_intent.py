from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.integrations.embeddings.embed_fn import EmbedFn
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.vocab_narrowing import DIRECT_MAX, narrow_candidates

# One value, or the several values a multi-pick param takes.
ParamAnswer = str | list[str]


class Provenance(StrEnum):
    """Where a bound value came from. A guess must stay distinguishable."""

    STATED = "stated"
    DEFAULTED = "defaulted"
    INFERRED = "inferred"


class IntentMatch(CamelModel):
    """A value together with how it was found."""

    value: ParamAnswer
    provenance: Provenance


# Decides a vocabulary value from the criterion text. Injected so this layer
# does not depend on `ai/`.
VocabResolver = Callable[
    [str, ParameterInfo, list[VocabOption]], Awaitable[ParamAnswer | None]
]

# Reads a value for a param that has no vocabulary.
FreeValueResolver = Callable[[str, ParameterInfo], Awaitable[str | None]]


@dataclass(frozen=True)
class ValueResolvers:
    """The two ways to read a value from a request."""

    vocab: VocabResolver | None = None
    free: FreeValueResolver | None = None


NO_RESOLVERS = ValueResolvers()


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
    """Map a free-text hint to a vocab value: exact match first, then substring."""
    h = hint.lower()
    for o in options:
        if h in (o.value.lower(), o.display.lower()):
            return o.value
    for o in options:
        if h in o.display.lower() or h in o.value.lower():
            return o.value
    return None


# How a contrast is written. The group before the marker is the one being
# tested; the group after it is the baseline.
_CONTRAST_MARKERS = (" vs ", " vs. ", " versus ", " compared to ", " against ")


def _comparator_in_text(options: list[VocabOption], text: str) -> str | None:
    """The group named on the comparator side of a written contrast.

    WDK computes fold change as comparator against reference, so taking the
    wrong side inverts the result. A plain substring match takes the longest
    name anywhere in the text, which is decided by word order rather than by
    which side it names.
    """
    low = text.lower()
    cut = min((low.index(m) for m in _CONTRAST_MARKERS if m in low), default=None)
    if cut is None:
        return _named_in_text(options, text)
    named = _named_in_text(options, text[:cut])
    if named is not None:
        return named
    # A side is usually written by the tokens that tell it apart, not by the
    # full option name. The best overlap wins, and only when it wins outright.
    left = _words(text[:cut])
    scored = sorted(
        ((len(_words(o.display or o.value) & left), o.value) for o in options),
        reverse=True,
    )
    if (
        scored
        and scored[0][0] > 0
        and (len(scored) == 1 or scored[0][0] > scored[1][0])
    ):
        return scored[0][1]
    return _named_in_text(options, text)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _named_in_text(options: list[VocabOption], text: str) -> str | None:
    """A vocab value whose name appears verbatim in the criterion text.

    The longest match wins.
    """
    low = text.lower()
    named = [
        o.value for o in options if o.display.lower() in low or o.value.lower() in low
    ]
    return max(named, key=len) if named else None


# Database accessions: Pfam, PANTHER, InterPro, GO, and EC numbers.
# The trailing boundary is a lookahead because an EC wildcard can end in a
# hyphen, which ``\b`` does not follow.
_ACCESSION_RE = re.compile(
    r"\b(?:[A-Z]{2,}[:_]?\d{3,}|\d+(?:\.[\d-]+){2,})(?![0-9A-Za-z])",
    re.IGNORECASE,
)


def names_absent_accession(options: list[VocabOption], text: str) -> bool:
    """The text names an accession and the vocabulary contains none of them.

    True stops the resolution chain so the caller opens a slot.
    """
    if not _ACCESSION_RE.search(text):
        return False
    return accession_in_text(options, text) is None


def sole_identifier_in_text(text: str) -> str | None:
    """The one database identifier the criterion names, if it names exactly one.

    Two identifiers in one criterion are ambiguous and stay unresolved.
    """
    tokens = {m.group(0) for m in _ACCESSION_RE.finditer(text)}
    return next(iter(tokens)) if len(tokens) == 1 else None


# A search term the request quotes. Longer spans are prose, not a term.
_QUOTED_RE = re.compile("['\"\u2018\u201c]([^'\"\u2019\u201d]{1,40})['\"\u2019\u201d]")
_MAX_TERM_WORDS = 4


def quoted_term_in_text(text: str) -> str | None:
    """The one term the request quotes, when it quotes exactly one.

    Two spans are ambiguous, and a long span is prose.
    """
    spans = {m.group(1).strip() for m in _QUOTED_RE.finditer(text)}
    terms = [s for s in spans if s and len(s.split()) <= _MAX_TERM_WORDS]
    return terms[0] if len(terms) == 1 and len(spans) == 1 else None


def _is_free_text_query(pi: ParameterInfo) -> bool:
    """A visible required param with no vocabulary: the search's own query."""
    return pi.is_visible and pi.required and not pi.is_number


def _identifier_for(
    pi: ParameterInfo, text: str, siblings: Sequence[ParameterInfo] = ()
) -> str | None:
    """The identifier in the text, when the param could hold it.

    A strain name matches the accession shape, so a numeric param must refuse
    anything that is not a number.
    """
    found = sole_identifier_in_text(text)
    if found is None:
        return None
    if (pi.is_number or pi.param_kind == "number") and not _is_numeric(found):
        return None
    if any(_offers(other, found) for other in siblings if other.name != pi.name):
        # A vocabulary that lists the identifier is where the value belongs.
        return None
    return found


def _offers(pi: ParameterInfo, value: str) -> bool:
    """Whether this param's vocabulary contains the value."""
    target = value.casefold()
    return any(
        o.value.casefold() == target
        or o.value.casefold().startswith((f"{target} ", f"{target}:"))
        for o in [*(pi.allowed_values or []), *pi.vocab_leaves]
    )


def _is_numeric(value: str) -> bool:
    """Whether a literal is a number WDK would accept, including EC-style dotted forms."""
    return bool(re.fullmatch(r"-?\d+(?:[.\d-]*\d|[.-]+)?", value))


def accession_in_text(options: list[VocabOption], text: str) -> str | None:
    """A vocabulary entry whose value carries an accession named in the text.

    An accession is an exact identifier and takes priority over a similarity
    match. Accessions absent from the vocabulary are not matched here.
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


# A contrast is between sample groups.
_CONTRAST_SUBJECT_MARKERS = ("sample", "group")
# WDK names an aggregation pair with the same reference/comparison markers.
_AGGREGATION_MARKERS = ("operation", "min_max_avg")


def is_aggregation_param(name: str) -> bool:
    """Whether a param selects how to aggregate a side rather than which samples
    that side contains."""
    return any(m in name.lower() for m in _AGGREGATION_MARKERS)


def contrast_role_of(name: str) -> Literal["reference", "comparison"] | None:
    """Contrast role from a param name or label alone."""
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
    """A key shared by the two halves of one contrast pair.

    The role marker is replaced by a slot, so the remaining stem keeps unrelated
    pairs independent.
    """
    low = name.lower()
    for marker in (*_COMPARISON_MARKERS, *_REFERENCE_MARKERS):
        if marker in low:
            return low.replace(marker, _ROLE_SLOT, 1)
    return low


def contrast_role(pi: ParameterInfo) -> Literal["reference", "comparison"] | None:
    """Which side of a differential contrast this sample selector fills.

    WDK computes fold change as comparator against reference, so the two sides
    are not interchangeable.
    """
    return contrast_role_of(f"{pi.name} {pi.display_name}")


_YES_NO = frozenset({"yes", "no"})


def _concept_from_param_name(name: str) -> str:
    """The thing a boolean param is asking about: ``isSyntenic`` -> "syntenic".

    The concept is what remains after the ``is`` or ``has`` prefix is removed.
    """
    stem = re.sub(r"^(is|has)[_-]?", "", name, flags=re.IGNORECASE)
    return re.sub(r"[_-]+", " ", stem).strip().lower()


def _boolean_polarity(pi: ParameterInfo, text: str) -> str | None:
    """Resolve a yes/no vocabulary from how the criterion phrases the concept.

    ``None`` when the criterion does not mention the concept. The param default
    applies there.
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
    """An organism named in the criterion text overrides the strategy-wide
    scope."""
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
    """Resolve a direction value.

    The full label is matched before the bare token, because the bare token is
    also a substring of the both-directions label.
    """
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
        # The group named in the criterion text is the subject of the contrast.
        named = _comparator_in_text(pi.allowed_values or [], intent.text)
        if named is not None:
            return named
    polarity = _boolean_polarity(pi, intent.text)
    if polarity is not None:
        return polarity
    if is_direction_param(pi.name):
        return _direction_value(pi, intent)
    return None


async def _resolved_without_vocabulary(
    pi: ParameterInfo,
    intent: ParamIntent,
    resolvers: ValueResolvers,
    siblings: Sequence[ParameterInfo] = (),
) -> IntentMatch | None:
    """Resolve a param with no options from a named rule, the identifier in the
    text, or the free-value resolver."""
    named = _rule_value(pi, intent) or _identifier_for(pi, intent.text, siblings)
    if named is None and _is_free_text_query(pi):
        named = quoted_term_in_text(intent.text)
    if named is not None:
        return IntentMatch(value=named, provenance=Provenance.STATED)
    if resolvers.free is None:
        return None
    read = await resolvers.free(intent.text, pi)
    if read is None:
        return None
    return IntentMatch(value=read, provenance=Provenance.INFERRED)


async def _resolved_from_vocabulary(
    pi: ParameterInfo,
    intent: ParamIntent,
    embed: EmbedFn,
    resolve_vocab: VocabResolver | None,
) -> IntentMatch | None:
    """Shortlist the vocabulary and let the resolver read it.

    Returns ``None`` when there is no resolver, nothing to choose from, or the
    criterion does not determine a value. ``None`` opens a slot and never falls
    through to a WDK default.
    """
    # A tree-box param holds its values in `vocab_leaves` and leaves
    # `allowed_values` empty.
    options = pi.allowed_values or pi.vocab_leaves
    if resolve_vocab is None or not options:
        return None
    if pi.param_kind == "multi-pick-vocabulary" and len(options) > DIRECT_MAX:
        # A set answer is trustworthy only if the resolver saw every option. An
        # incomplete answer over a shortlist still validates.
        return None
    candidates = await narrow_candidates(options, intent.text, embed=embed)
    answer = await resolve_vocab(intent.text, pi, candidates)
    validated = _validated_answer(answer, pi, candidates)
    if validated is None:
        return None
    return IntentMatch(value=validated, provenance=Provenance.INFERRED)


def _validated_answer(
    answer: ParamAnswer | None,
    pi: ParameterInfo,
    candidates: list[VocabOption],
) -> ParamAnswer | None:
    """Every element must be a candidate, and a single-pick may name only one.

    A partly valid multi-pick is refused whole.
    """
    if answer is None:
        return None
    wanted = [answer] if isinstance(answer, str) else answer
    if not wanted:
        return None
    if pi.param_kind != "multi-pick-vocabulary" and len(wanted) > 1:
        return None
    valid = {o.value for o in candidates}
    if any(value not in valid for value in wanted):
        return None
    return wanted if pi.param_kind == "multi-pick-vocabulary" else wanted[0]


async def map_intent_to_value(
    pi: ParameterInfo,
    intent: ParamIntent,
    *,
    embed: EmbedFn,
    resolvers: ValueResolvers = NO_RESOLVERS,
    siblings: Sequence[ParameterInfo] = (),
) -> IntentMatch | None:
    """Map a criterion's intent to a valid vocab value, rules first and the
    injected resolver second. ``None`` means ambiguous, and the caller opens a
    slot. The match carries its provenance so a guess stays distinguishable from
    a value the request states."""
    # `allowed_values` is capped, so an accession in a large vocabulary appears
    # only in `vocab_leaves`.
    if not pi.allowed_values and not pi.vocab_leaves:
        # Without a vocabulary there is nothing to match an identifier against,
        # so the literal in the text is the value and WDK validates it.
        return await _resolved_without_vocabulary(pi, intent, resolvers, siblings)
    named = accession_in_text(
        [*(pi.allowed_values or []), *pi.vocab_leaves], intent.text
    )
    if named is not None:
        return IntentMatch(value=named, provenance=Provenance.STATED)
    if names_absent_accession(
        [*(pi.allowed_values or []), *pi.vocab_leaves], intent.text
    ):
        return None
    rule = _rule_value(pi, intent)
    if rule is not None:
        return IntentMatch(value=rule, provenance=Provenance.STATED)
    if contrast_role(pi) == "reference":
        # The criterion text names the comparator side. A semantic match into
        # the reference slot inverts the contrast.
        return None
    return await _resolved_from_vocabulary(pi, intent, embed, resolvers.vocab)
