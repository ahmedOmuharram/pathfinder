"""Deterministic resolution of a WDK search's parameter dependency DAG."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace

from pydantic import (
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
)
from pydantic import ValidationError as PydanticValidationError

from pathfinder.domain.parameters.values import (
    FilterTermClause,
    FilterValue,
    ParamValue,
    param_value_from_raw,
    to_wire,
)
from pathfinder.domain.parameters.wdk_vocab import VocabOption, match_exact_option
from pathfinder.domain.strategy.operational_spec import OpenSlot
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_formatting import (
    FilterFieldInfo,
    ParameterInfo,
    format_param_info_typed,
)
from pathfinder.services.catalog.param_intent import (
    IntentMatch,
    ParamIntent,
    Provenance,
    contrast_pair_key,
    contrast_role,
    is_aggregation_param,
    match_option,
)
from pathfinder.services.catalog.search_context import (
    get_search_params_under_context,
)
from pathfinder.services.wdk import get_wdk_client

_SCALAR_DEFAULTABLE: frozenset[str] = frozenset(
    {"number", "string", "date", "timestamp", "single-pick-vocabulary"}
)
_MAX_RESOLVE_DEPTH = 6
_MAX_SLOT_OPTIONS = 20
# A vocabulary needs two or more options before a shared value is a real choice.
_MIN_VOCAB_SIZE_FOR_DEGENERACY = 2


def _vocab_signature(info: ParameterInfo) -> str | None:
    """Returns a stable signature of the option set, or None when there is no vocabulary."""
    values = info.vocabulary()
    if not values:
        return None
    return "|".join(sorted(o.value for o in values))


# An answered open slot holds one value, or a list for a multi-pick slot.
OverrideValue = str | list[str]
OverrideMap = dict[str, OverrideValue]


class UnknownParameterError(ValidationError):
    """An override names a parameter the search does not have."""

    def __init__(self, unknown: list[str], valid: list[str]) -> None:
        self.unknown = unknown
        self.valid = valid
        super().__init__(
            title="Unknown parameter",
            detail=(
                f"No such parameter(s) on this search: {unknown}. Valid names: {valid}."
            ),
            errors=[{"param": name} for name in unknown],
        )


def _refuse_unknown_overrides(
    infos: list[ParameterInfo], overrides: OverrideMap, *, first_pass: bool
) -> None:
    """Refuses an override that names no parameter of the search.

    The search names every parameter on the first fetch, so a name the walk would
    never read is a mistake, not a value to drop.
    """
    if not first_pass or not overrides:
        return
    names = {i.name for i in infos}
    unknown = sorted(set(overrides) - names)
    if unknown:
        raise UnknownParameterError(unknown, sorted(names))


def _sole_claim(value: OverrideValue | None) -> str | None:
    """Returns the single vocabulary option this resolution claims.

    A multi-pick selection claims no single option.
    """
    return None if isinstance(value, list) else value


def param_value_for(pi: ParameterInfo, raw: object) -> ParamValue:
    """Builds a ParamValue from a chosen term using the param's ParamKind."""
    return param_value_from_raw(raw, pi.param_kind)


def _single_valid_value(info: ParameterInfo) -> str | None:
    """The one value a vocabulary of exactly one entry allows.

    ``None`` when the param has no vocabulary or offers a choice.
    """
    values = info.vocabulary()
    return values[0].value if len(values) == 1 else None


ParamFetcher = Callable[[dict[str, str]], Awaitable[list[ParameterInfo]]]


def wdk_fetch_at(site_id: str, record_type: str, search_name: str) -> ParamFetcher:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        resp = await get_search_params_under_context(
            get_wdk_client(site_id), record_type, search_name, context
        )
        params = resp.search_data.parameters or []
        return format_param_info_typed(params)

    return fetch_at


class ResolvedParam(CamelModel):
    """One bound value with the reason it holds that value."""

    value: ParamValue
    provenance: Provenance


class Unread(CamelModel):
    """A numeric param left with no value while the request states a quantity for it.

    The caller reads the quantity out of the request instead of asking the user,
    so this is not an open slot.
    """

    param_name: str


class ResolvedParams(CamelModel):
    """Build-ready params, plus open slots and the required params that stay unresolved."""

    params: dict[str, ParamValue] = Field(default_factory=dict)
    provenance: dict[str, Provenance] = Field(default_factory=dict)
    open_slots: list[OpenSlot] = Field(default_factory=list)
    unresolved_required: list[str] = Field(default_factory=list)
    # Params the request states a quantity for and nothing bound.
    unread: list[str] = Field(default_factory=list)

    def defaulted(self) -> list[str]:
        """Params holding the search default rather than a stated value."""
        return sorted(
            name
            for name, source in self.provenance.items()
            if source is Provenance.DEFAULTED
        )


def _build_value(info: ParameterInfo, value: OverrideValue | None) -> ParamValue | None:
    """Coerces a chosen value into the param's typed value, or None when the kind
    rejects it. Filter params resolve elsewhere."""
    if value is None:
        return None
    try:
        return param_value_for(info, value)
    except ValueError:
        return None


def _apply_override(info: ParameterInfo, value: OverrideValue) -> OverrideValue:
    """Matches a proposed value to the param's vocabulary entry, or passes it through
    for WDK to validate. A list value matches each element on its own.

    The match is exact on the term, on the label, or on a leading accession
    exactly one entry carries. Any other substring names a different entry.
    """
    options = info.vocabulary()
    if not options:
        return value
    if isinstance(value, list):
        return [match_exact_option(options, v) or v for v in value]
    return match_exact_option(options, value) or value


def _match_filter_field(info: ParameterInfo, hint: str) -> FilterFieldInfo | None:
    """Resolves a facet by name. An exact term or display match wins over a substring."""
    hint_l = hint.strip().lower()
    for field in info.filter_fields:
        if hint_l in (field.term.lower(), field.display.lower()):
            return field
    return next(
        (
            field
            for field in info.filter_fields
            if hint_l in field.term.lower() or hint_l in field.display.lower()
        ),
        None,
    )


def _match_filter_values(
    field: FilterFieldInfo, raw_values: list[str]
) -> list[JsonValue]:
    """Matches each requested member against the facet's values. An unknown member
    passes through for WDK to validate."""
    options = [VocabOption(value=v, display=v) for v in field.values]
    return [match_option(options, v) or v for v in raw_values]


class _RawFilterClause(CamelModel):
    """A clause as the model emits it, which may be partial. The type, isRange and
    includeUnknown fields come from the ontology instead."""

    model_config = ConfigDict(extra="ignore")
    field: str = ""
    value: list[JsonValue] = Field(default_factory=list)

    @field_validator("value", mode="before")
    @classmethod
    def _as_member_list(cls, v: JsonValue) -> JsonValue:
        if v is None:
            return []
        return v if isinstance(v, list) else [v]


class _RawFilterInput(CamelModel):
    """The WDK filters wrapper. Clauses may be partial and bind to the ontology later."""

    model_config = ConfigDict(extra="ignore")
    filters: list[_RawFilterClause] = Field(default_factory=list)


def _enrich_clause(
    info: ParameterInfo, raw: _RawFilterClause
) -> FilterTermClause | None:
    """Binds a clause to an ontology facet and matches its members to the facet values.
    A clause for an unknown facet passes through for WDK to validate."""
    if not raw.field:
        return None
    facet = _match_filter_field(info, raw.field)
    if facet is None:
        return FilterTermClause(field=raw.field, value=raw.value)
    return FilterTermClause(
        field=facet.term,
        type=facet.type,
        is_range=facet.is_range,
        value=_match_filter_values(facet, [str(v) for v in raw.value]),
    )


def _filter_from_json(info: ParameterInfo, text: str) -> FilterValue:
    try:
        parsed = _RawFilterInput.model_validate_json(text)
    except PydanticValidationError:
        return FilterValue()
    clauses = [
        clause
        for raw in parsed.filters
        if (clause := _enrich_clause(info, raw)) is not None
    ]
    return FilterValue(filters=clauses)


_CONTRAST_PREFIXES: tuple[tuple[str, str], ...] = (("ref", "comp"), ("comp", "ref"))


def _has_contrast_sibling(info: ParameterInfo, infos: list[ParameterInfo]) -> bool:
    """Reports whether this filter param is one half of a reference and comparison
    sample pair. Both halves taking the empty all-samples filter is a degenerate
    contrast, so the pair is surfaced instead of auto-resolved."""
    name = info.name
    for this, other in _CONTRAST_PREFIXES:
        prefix = f"{this}_"
        if name.startswith(prefix):
            sibling = f"{other}_{name[len(prefix) :]}"
            return any(i.name == sibling and i.param_kind == "filter" for i in infos)
    return False


def _contrast_open_slot(info: ParameterInfo) -> OpenSlot:
    return OpenSlot(
        param_name=info.name,
        question=(
            f"Choose the sample group for {info.display_name}: a "
            f"reference-vs-comparison contrast needs DISTINCT groups on each "
            f"side, not all samples on both."
        ),
        options=[
            f"{field.term}={value}"
            for field in info.filter_fields
            for value in field.values
        ][:_MAX_SLOT_OPTIONS],
    )


def _resolve_filter_param(
    info: ParameterInfo, infos: list[ParameterInfo], overrides: OverrideMap
) -> FilterValue | OpenSlot:
    """Resolves a filter param to a value, or returns an OpenSlot for an unspecified
    half of a contrast pair."""
    override = overrides.get(info.name)
    if isinstance(override, list):
        raise ValidationError(
            title="Invalid parameter value",
            detail=(
                f"Parameter '{info.name}' is a filter, which selects members of "
                f"ONE facet. A bare list names no facet. Pass "
                f"'<facet>=<value1>,<value2>' instead, e.g. "
                f"'{info.filter_fields[0].term if info.filter_fields else 'Sample type'}"
                f"={','.join(override[:2])}'."
            ),
            errors=[{"param": info.name, "value": list(override)}],
        )
    if override is None and _has_contrast_sibling(info, infos):
        return _contrast_open_slot(info)
    return _resolve_filter(info, override)


def _resolve_filter(info: ParameterInfo, override: str | None) -> FilterValue:
    """Builds a filter param value. The WDK default is the empty filter set, which
    includes all samples. An override is either WDK filter JSON or the shorthand
    facet=value1,value2, and both select members of one ontology facet."""
    if not override:
        return FilterValue()
    text = override.strip()
    if text.startswith("{"):
        return _filter_from_json(info, text)
    field_hint, sep, raw = text.partition("=")
    if not sep:
        return FilterValue()
    field = _match_filter_field(info, field_hint)
    if field is None:
        return FilterValue()
    raw_values = [v.strip() for v in raw.split(",") if v.strip()]
    if not raw_values:
        return FilterValue()
    return FilterValue(
        filters=[
            FilterTermClause(
                field=field.term,
                type=field.type,
                is_range=field.is_range,
                value=_match_filter_values(field, raw_values),
            )
        ]
    )


def _resolve_one(info: ParameterInfo, overrides: OverrideMap) -> IntentMatch | None:
    """An override binds as stated; a single valid value binds as the search's own.

    ``None`` leaves the param to the scalar default or to an open slot.
    """
    if info.name in overrides:
        return IntentMatch(
            value=_apply_override(info, overrides[info.name]),
            provenance=Provenance.STATED,
        )
    sole = _single_valid_value(info)
    if sole is not None:
        return IntentMatch(value=sole, provenance=Provenance.DEFAULTED)
    return None


def _is_free_text_query(info: ParameterInfo) -> bool:
    """Reports whether the param is the search's own text query.

    WDK puts an example in the default value of these params, so the default must not
    be inherited. Hidden params and numeric bounds carry real defaults and are excluded.
    """
    return (
        info.param_kind == "string"
        and not info.is_number
        and info.is_visible
        and info.required
        and not info.vocabulary()
    )


# Database accessions: Pfam, PANTHER, InterPro, GO, and EC numbers. The trailing
# boundary is a lookahead because an EC wildcard can end in a hyphen, which
# ``\b`` does not follow.
_ACCESSION_RE = re.compile(
    r"\b(?:[A-Z]{2,}[:_]?\d{3,}|\d+(?:\.[\d-]+){2,})(?![0-9A-Za-z])",
    re.IGNORECASE,
)
_QUANTITY_RE = re.compile(r"(?<![0-9A-Za-z_.:-])\d+(?:\.\d+)?(?![0-9A-Za-z_:-])")


def _states_a_quantity(
    info: ParameterInfo, text: str, siblings: tuple[ParameterInfo, ...]
) -> bool:
    """Whether the request names a number this numeric param could answer.

    A default is a reasonable answer to a question nobody asked. It is not a
    reasonable answer to one the request already answered, so a stated quantity
    holds the default back and the param is reported unread instead.
    """
    if not info.is_number or not info.default_value or not text:
        return False
    without_identifiers = _ACCESSION_RE.sub(" ", text)
    stated = {m.group(0) for m in _QUANTITY_RE.finditer(without_identifiers)}
    if not stated:
        return False
    # With several numeric slots on one search there is nothing to say which
    # one the number belongs to. Grouping the ends of a range together was
    # measured against the gold corpus and cost seven correct defaults while
    # preventing no wrong value, so the slots are counted as they come.
    numeric_slots = [s for s in siblings if s.is_number and s.default_value]
    if len(numeric_slots) > 1:
        return False
    # A default that equals a stated quantity is the stated quantity.
    return not any(_same_number(value, info.default_value) for value in stated)


def _same_number(left: str, right: str) -> bool:
    try:
        return float(left) == float(right)
    except ValueError:
        return False


def _scalar_default(info: ParameterInfo) -> str | None:
    """Returns the param default when the kind is a defaultable scalar or vocabulary.
    The caller applies the degenerate-pair check."""
    if not info.default_value or info.param_kind not in _SCALAR_DEFAULTABLE:
        return None
    if _is_free_text_query(info):
        return None
    return info.default_value


def _curated_multi_default(info: ParameterInfo) -> list[str] | None:
    """Returns a multi-pick param's non-empty list default, which is the curated
    selection. A param with an empty default returns None, so an override or an open
    slot decides it.
    """
    if info.param_kind != "multi-pick-vocabulary" or not info.default_value:
        return None
    try:
        parsed = json.loads(info.default_value)
    except TypeError, ValueError:
        return None
    if not isinstance(parsed, list) or not parsed:
        return None
    return [str(v) for v in parsed]


class _VocabLedger(CamelModel):
    """Tracks which vocabulary values siblings from the same option set have taken.

    Two params from one option set must not take the same value. The ledger also
    records whether an override stated the value or a default supplied it.
    """

    taken: dict[str, set[str]] = Field(default_factory=dict)
    pinned: dict[str, set[str]] = Field(default_factory=dict)
    claimant: dict[str, dict[str, str]] = Field(default_factory=dict)

    def claim(self, signature: str, value: str, name: str, *, pinned: bool) -> None:
        self.taken.setdefault(signature, set()).add(value)
        self.claimant.setdefault(signature, {})[value] = name
        if pinned:
            self.pinned.setdefault(signature, set()).add(value)

    def duplicates_sibling(self, info: ParameterInfo, value: str) -> bool:
        """Reports whether a sibling from the identical vocabulary already took the
        value. A single-option vocabulary is exempt because no other value exists.
        """
        if is_aggregation_param(f"{info.name} {info.display_name}"):
            # Aggregation selectors are not a contrast. The same operation on both
            # sides is correct.
            return False
        if len(info.vocabulary()) < _MIN_VOCAB_SIZE_FOR_DEGENERACY:
            return False
        signature = _vocab_signature(info)
        return signature is not None and value in self.taken.get(signature, set())

    def sole_remaining_option(
        self, info: ParameterInfo, taken_value: str
    ) -> str | None:
        """Returns the single option left once siblings take theirs.

        This applies only when an explicit override pinned the colliding value. A
        defaulted sibling gives no direction, so the caller asks the user instead.
        """
        signature = _vocab_signature(info)
        if signature is None or taken_value not in self.pinned.get(signature, set()):
            return None
        taken = self.taken.get(signature, set())
        remaining = [o.value for o in info.vocabulary() if o.value not in taken]
        return remaining[0] if len(remaining) == 1 else None

    def sole_remaining_after_authoritative(self, info: ParameterInfo) -> str | None:
        """Returns the one option left once an authoritative sibling takes its own.

        A reference slot has no candidate of its own, so a single remaining option is
        the forced answer.
        """
        signature = _vocab_signature(info)
        if signature is None or not self.pinned.get(signature):
            return None
        taken = self.taken.get(signature, set())
        remaining = [o.value for o in info.vocabulary() if o.value not in taken]
        return remaining[0] if len(remaining) == 1 else None

    def release_default_holding(
        self, info: ParameterInfo, wanted: str, overrides: OverrideMap
    ) -> str | None:
        """Frees a value from a defaulted claimant so an override can take it.

        An override is authoritative and a default is not. Returns the evicted param
        name so the caller unbinds and re-resolves it.
        """
        signature = _vocab_signature(info)
        if signature is None:
            return None
        holder = self.claimant.get(signature, {}).get(wanted)
        if holder is None or holder == info.name or holder in overrides:
            return None
        self.taken.get(signature, set()).discard(wanted)
        self.claimant.get(signature, {}).pop(wanted, None)
        self.pinned.setdefault(signature, set()).add(wanted)
        return holder


def _open_slot(info: ParameterInfo) -> OpenSlot:
    """Builds a question for the user."""
    options = info.vocabulary()
    return OpenSlot(
        param_name=info.name,
        question=f"Choose a value for {info.display_name}",
        options=[o.value for o in options][:_MAX_SLOT_OPTIONS],
    )


@dataclass(frozen=True)
class _Resolution:
    """Everything the walk needs to decide one parameter's value."""

    intent: ParamIntent
    overrides: OverrideMap
    siblings: tuple[ParameterInfo, ...] = ()


def _settle_value(
    info: ParameterInfo,
    value: OverrideValue | None,
    ledger: _VocabLedger,
    *,
    is_user_choice: bool,
    default_held_back: bool,
) -> OverrideValue | None:
    """Apply the scalar default and the degenerate-pair rules to a read value."""
    if value is None and not default_held_back:
        value = _scalar_default(info)
    if value is None and contrast_role(info) == "reference":
        value = ledger.sole_remaining_after_authoritative(info)
    claimed = _sole_claim(value)
    if (
        claimed is not None
        and not is_user_choice
        and ledger.duplicates_sibling(info, claimed)
    ):
        # A sibling holds this value. Take the forced remainder when one option is left.
        return ledger.sole_remaining_option(info, claimed)
    return value


def _resolve_nonfilter(
    info: ParameterInfo,
    res: _Resolution,
    ledger: _VocabLedger,
) -> ResolvedParam | OpenSlot | Unread | None:
    """Resolves a non-filter param from an override, then a single valid value, then
    the scalar default, then an open slot. An override outranks the degenerate-pair
    check. Unread means the request states a quantity the default must not answer.
    None means the param is optional and unset."""
    is_user_choice = info.name in res.overrides
    if not is_user_choice:
        curated = _curated_multi_default(info)
        if curated is not None:
            return ResolvedParam(
                value=param_value_for(info, curated), provenance=Provenance.DEFAULTED
            )
    match = _resolve_one(info, res.overrides)
    provenance = match.provenance if match is not None else Provenance.DEFAULTED
    read = match.value if match is not None else None
    held_back = read is None and _states_a_quantity(info, res.intent.text, res.siblings)
    value = _settle_value(
        info,
        read,
        ledger,
        is_user_choice=is_user_choice,
        default_held_back=held_back,
    )
    if value is None and held_back:
        return Unread(param_name=info.name)
    resolved = _build_value(info, value)
    if resolved is None or value is None:
        return _open_slot(info) if info.required else None
    signature = _vocab_signature(info)
    if signature is not None:
        # Only a supplied value is authoritative. A scalar default is not.
        claimed = _sole_claim(value)
        if claimed is not None:
            ledger.claim(signature, claimed, info.name, pinned=is_user_choice)
    return ResolvedParam(value=resolved, provenance=provenance)


def _awaits_comparator(
    info: ParameterInfo, infos: list[ParameterInfo], resolved: set[str]
) -> bool:
    """Reports whether a reference slot must wait for its comparator sibling. The
    baseline is defined by the value the comparator does not take.
    """
    if contrast_role(info) != "reference":
        return False
    # Pair on the name stem. A vocabulary signature does not match while the comparator
    # still carries its pre-parent option set, and a bare role match couples
    # unrelated pairs.
    key = contrast_pair_key(info.name)
    return any(
        other.name not in resolved
        and other.name != info.name
        and contrast_role(other) == "comparison"
        and contrast_pair_key(other.name) == key
        for other in infos
    )


def _evict_for_override(
    info: ParameterInfo,
    overrides: OverrideMap,
    *,
    ledger: _VocabLedger,
    params: dict[str, ParamValue],
    context: dict[str, str],
    seen: set[str],
) -> None:
    """Unbinds a defaulted param that holds the value this override wants, so it
    re-resolves against the claimed vocabulary."""
    if info.name not in overrides:
        return
    wanted = _sole_claim(_apply_override(info, overrides[info.name]))
    if wanted is None:
        return
    evicted = ledger.release_default_holding(info, wanted, overrides)
    if evicted is None:
        return
    params.pop(evicted, None)
    context.pop(evicted, None)
    seen.discard(evicted)


def _resolution_rank(info: ParameterInfo, overrides: OverrideMap) -> tuple[int, int]:
    """Orders resolution within a pass so authoritative values claim their vocabulary
    slot first: overrides, then comparators, then the rest, then references.
    """
    role = contrast_role(info)
    role_rank = {"comparison": 0, "reference": 2}.get(role or "", 1)
    return (0 if info.name in overrides else 1, role_rank)


def _defer_to_next_pass(
    info: ParameterInfo,
    *,
    context: dict[str, str],
    resolved_this_pass: set[str],
) -> bool:
    """Reports whether to skip the param until the walk re-fetches under a new context.

    A param whose vocabulary parent is unresolved, or resolved during this pass, has a
    stale option set. The next pass fetches the real vocabulary.
    """
    depends_on = set(info.vocab_depends_on or [])
    if depends_on - context.keys():
        return True
    return bool(depends_on & resolved_this_pass)


async def resolve_params_with_intent(
    *,
    fetch_at: ParamFetcher,
    intent: ParamIntent,
    overrides: OverrideMap | None = None,
) -> ResolvedParams:
    """Walks the dependency DAG and resolves each param from an override, an automatic
    value, the scalar default, or an open slot. Re-fetches after each pick so dependent
    params surface.

    An override that names no parameter of the search raises ``UnknownParameterError``.
    """
    overrides = overrides or {}
    context: dict[str, str] = {}
    params: dict[str, ParamValue] = {}
    open_slots: list[OpenSlot] = []
    unresolved: list[str] = []
    unread: list[str] = []
    seen: set[str] = set()
    provenance: dict[str, Provenance] = {}
    ledger = _VocabLedger()
    resolution = _Resolution(intent=intent, overrides=overrides)
    for pass_index in range(_MAX_RESOLVE_DEPTH):
        infos = await fetch_at(context)
        _refuse_unknown_overrides(infos, overrides, first_pass=pass_index == 0)
        # Siblings decide whether one numeric param owns a stated quantity.
        resolution = replace(resolution, siblings=tuple(infos))
        progressed = False
        # Overridden params resolve first so an authoritative value claims its
        # vocabulary slot before a sibling defaults onto it. Eviction covers dependent
        # params, which a later pass resolves after a default is already bound.
        resolved_this_pass: set[str] = set()
        for info in sorted(infos, key=lambda i: _resolution_rank(i, overrides)):
            _evict_for_override(
                info,
                overrides,
                ledger=ledger,
                params=params,
                context=context,
                seen=seen,
            )
            if info.name in seen or _defer_to_next_pass(
                info, context=context, resolved_this_pass=resolved_this_pass
            ):
                continue
            if _awaits_comparator(info, infos, set(params) | set(unresolved)):
                continue
            outcome: ResolvedParam | OpenSlot | Unread | None
            if info.param_kind == "filter":
                filtered = _resolve_filter_param(info, infos, overrides)
                outcome = (
                    filtered
                    if isinstance(filtered, OpenSlot)
                    else ResolvedParam(
                        value=filtered,
                        provenance=(
                            Provenance.STATED
                            if info.name in overrides
                            else Provenance.DEFAULTED
                        ),
                    )
                )
            else:
                outcome = _resolve_nonfilter(info, resolution, ledger)
            if isinstance(outcome, Unread):
                unread.append(outcome.param_name)
                unresolved.append(outcome.param_name)
            elif isinstance(outcome, OpenSlot):
                open_slots.append(outcome)
                unresolved.append(info.name)
            elif outcome is not None:
                params[info.name] = outcome.value
                provenance[info.name] = outcome.provenance
                context[info.name] = to_wire(outcome.value)
                resolved_this_pass.add(info.name)
            seen.add(info.name)
            progressed = True
        if not progressed:
            break
    return ResolvedParams(
        params=params,
        provenance=provenance,
        open_slots=open_slots,
        unresolved_required=unresolved,
        unread=unread,
    )
