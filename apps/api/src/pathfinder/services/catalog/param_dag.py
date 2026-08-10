"""Deterministic resolution of a WDK search's parameter dependency DAG."""

from __future__ import annotations

import graphlib
import json
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

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
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.domain.strategy.operational_spec import OpenSlot
from pathfinder.integrations.veupathdb.search_context import (
    get_search_params_under_context,
)
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_formatting import (
    FilterFieldInfo,
    ParameterInfo,
    format_param_info_typed,
)
from pathfinder.services.catalog.param_intent import (
    EmbedFn,
    ParamIntent,
    contrast_pair_key,
    contrast_role,
    is_aggregation_param,
    map_intent_to_value,
    match_option,
)
from pathfinder.services.wdk import get_wdk_client

_SCALAR_DEFAULTABLE: frozenset[str] = frozenset(
    {"number", "string", "date", "timestamp", "single-pick-vocabulary"}
)
_MAX_RESOLVE_DEPTH = 6
_MAX_SLOT_OPTIONS = 20
# A vocabulary needs at least two options before a shared value can be a
# *choice* the user could have made differently.
_MIN_VOCAB_SIZE_FOR_DEGENERACY = 2


def _vocab_signature(info: ParameterInfo) -> str | None:
    """A stable signature of a vocab param's option set, or ``None`` for params
    whose default can never form a degenerate pair (scalars / no vocab)."""
    values = info.allowed_values
    if not values:
        return None
    return "|".join(sorted(o.value for o in values))


# An answered open slot: one value, or the several a multi-pick slot takes.
OverrideValue = str | list[str]
OverrideMap = dict[str, OverrideValue]


def _sole_claim(value: OverrideValue | None) -> str | None:
    """The single vocabulary option this resolution claims, if it claims one.

    The vocab ledger exists to stop the two halves of a ref/comp contrast
    selecting the SAME option. That question only has meaning for a scalar
    pick; a multi-pick selection of 13 time points claims no single option and
    has no contrast sibling to degenerate against.
    """
    return None if isinstance(value, list) else value


def param_value_for(pi: ParameterInfo, raw: object) -> ParamValue:
    """Single seam: build a ``ParamValue`` from a chosen term using the param's
    real ``ParamKind`` (multi-pick terms wrap to a 1-element list; scalars cast)."""
    return param_value_from_raw(raw, pi.param_kind)


class AutoResolved(CamelModel):
    """A param with a single valid value — set in code, no choice to make."""

    kind: Literal["auto_resolved"] = "auto_resolved"
    name: str
    value: str


class Choice(CamelModel):
    """A multi-valued param — the model maps intent to a value, or it becomes
    an editable plan slot for the user."""

    kind: Literal["choice"] = "choice"
    name: str
    options: list[VocabOption] = Field(default_factory=list)
    default: str | None = None
    help: str = ""


ParamTier = Annotated[AutoResolved | Choice, Field(discriminator="kind")]


def classify_param(info: ParameterInfo) -> ParamTier:
    values = info.allowed_values or []
    if len(values) == 1:
        return AutoResolved(name=info.name, value=values[0].value)
    return Choice(
        name=info.name,
        options=values,
        default=info.default_value,
        help=info.help,
    )


ParamFetcher = Callable[[dict[str, str]], Awaitable[list[ParameterInfo]]]


class DagResolution(CamelModel):
    auto_resolved: list[AutoResolved] = Field(default_factory=list)
    choices: list[Choice] = Field(default_factory=list)
    param_infos: list[ParameterInfo] = Field(default_factory=list)


async def resolve_dag(
    *,
    fetch_at: ParamFetcher,
    chosen_values: dict[str, str] | None = None,
) -> DagResolution:
    context = dict(chosen_values or {})
    infos = await fetch_at(context)
    last_context = dict(context)
    required = {i.name: i for i in infos if i.required}
    graph = {
        name: set(info.vocab_depends_on or []) & required.keys()
        for name, info in required.items()
    }
    fill_order = list(graphlib.TopologicalSorter(graph).static_order())

    auto_resolved: list[AutoResolved] = []
    choices: list[Choice] = []
    param_infos: list[ParameterInfo] = []
    for name in fill_order:
        if context != last_context:
            infos = await fetch_at(context)
            last_context = dict(context)
        info = next((i for i in infos if i.name == name), None)
        if info is None:
            continue
        param_infos.append(info)
        tier = classify_param(info)
        if isinstance(tier, AutoResolved):
            context[name] = tier.value
            auto_resolved.append(tier)
        else:
            choices.append(tier)
    return DagResolution(
        auto_resolved=auto_resolved, choices=choices, param_infos=param_infos
    )


def _wdk_fetch_at(site_id: str, record_type: str, search_name: str) -> ParamFetcher:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        resp = await get_search_params_under_context(
            get_wdk_client(site_id), record_type, search_name, context
        )
        params = resp.search_data.parameters or []
        return format_param_info_typed(params)

    return fetch_at


async def resolve_parameter_dag(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    chosen_values: dict[str, str] | None = None,
) -> DagResolution:
    return await resolve_dag(
        fetch_at=_wdk_fetch_at(site_id, record_type, search_name),
        chosen_values=chosen_values,
    )


class ResolvedParams(CamelModel):
    """Build-ready params (Tier-1/2) plus Tier-3 slots and still-unresolved
    required param names for the binding guard."""

    params: dict[str, ParamValue] = Field(default_factory=dict)
    open_slots: list[OpenSlot] = Field(default_factory=list)
    unresolved_required: list[str] = Field(default_factory=list)


def _build_value(info: ParameterInfo, value: OverrideValue | None) -> ParamValue | None:
    """Coerce a chosen string into the param's typed value, or ``None`` when it
    can't (e.g. a plain answer for a structured 'dataset'/'step' selector) — so
    the param degrades to an open slot instead of crashing set_criterion. Filter
    params never reach here; the walk resolves them via ``_resolve_filter``."""
    if value is None:
        return None
    try:
        return param_value_for(info, value)
    except ValueError:
        return None


def _apply_override(info: ParameterInfo, value: OverrideValue) -> OverrideValue:
    """A user-supplied value for an open slot. Match it to the param's
    vocabulary (so 'uninfected' resolves to the exact option, or a bare
    'Plasmodium vivax' snaps to the tree-box leaf 'Plasmodium vivax P01') when
    there is one; otherwise pass the value through for WDK to validate. Tree-box
    params carry their values in ``vocab_leaves`` rather than ``allowed_values``.

    A multi-pick answer arrives as a list and stays one: each element snaps
    independently. Collapsing it to a single string made the whole serialized
    array one candidate option, which matched nothing and was reported back to
    the model as its own answer being invalid."""
    options = info.allowed_values or info.vocab_leaves
    if not options:
        return value
    if isinstance(value, list):
        return [match_option(options, v) or v for v in value]
    return match_option(options, value) or value


def _match_filter_field(info: ParameterInfo, hint: str) -> FilterFieldInfo | None:
    """Resolve a facet by name: exact term/display first, then substring."""
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
    """Match each requested member against the facet's real values (so 'culture'
    snaps to the exact option), passing unknowns through for WDK to validate."""
    options = [VocabOption(value=v, display=v) for v in field.values]
    return [match_option(options, v) or v for v in raw_values]


class _RawFilterClause(CamelModel):
    """A clause as the model emits it — possibly partial (just field + a scalar
    or list value). type/isRange/includeUnknown are ignored here and re-derived
    from the authoritative ontology."""

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
    """The model's natural filter override — the WDK ``{"filters": [...]}``
    wrapper. Clauses may be partial; they are bound to the ontology downstream."""

    model_config = ConfigDict(extra="ignore")
    filters: list[_RawFilterClause] = Field(default_factory=list)


def _enrich_clause(
    info: ParameterInfo, raw: _RawFilterClause
) -> FilterTermClause | None:
    """Bind a (possibly partial) clause to a real ontology facet: take the
    facet's term/type/isRange and match the requested members to its values.
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
    """Whether this filter param is one half of a differential search's
    reference/comparison sample pair (WDK names them ``ref_samples_*`` /
    ``comp_samples_*``). Both defaulting to the empty 'all samples' filter is a
    degenerate all-vs-all contrast → zero DE genes (the filter analog of a DESeq
    ref==comp), so the pair must be surfaced rather than auto-resolved to all."""
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
    """Resolve a filter param to a value, or surface an ``OpenSlot`` when it is
    an unspecified half of a ref/comp contrast pair (both halves defaulting to
    'all samples' is a degenerate all-vs-all contrast)."""
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
    """Build a filter param value. A filter restricts the search to a faceted
    subset of the dataset's samples/strains; WDK's canonical default is the
    empty filter set (include all) — the right resolution unless the user named
    a specific facet restriction. An override is either the model's natural WDK
    filter JSON (a ``{"filters": [...]}`` string, enriched from the ontology) or
    the shorthand ``<facet>=<v1>,<v2>``; both select members of one ontology
    facet, typed from that facet and matched to its real values."""
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


async def _resolve_one(
    info: ParameterInfo,
    intent: ParamIntent,
    embed: EmbedFn,
    overrides: OverrideMap,
) -> OverrideValue | None:
    """Tier-0 user override (an answered open slot) → Tier-1 (single valid
    value) → Tier-2 (intent). Scalar-defaulting is decided by the walk so it
    can refuse a degenerate duplicate selection."""
    if info.name in overrides:
        return _apply_override(info, overrides[info.name])
    tier = classify_param(info)
    if isinstance(tier, AutoResolved):
        return tier.value
    return await map_intent_to_value(info, intent, embed=embed)


def _is_free_text_query(info: ParameterInfo) -> bool:
    """A visible, required, vocabulary-less string param: the search's own text
    query. WDK ships an *example* in ``default_value`` for these (GenesByText
    offers ``*reductase``), so inheriting it silently rewrites the question --
    an odorant-binding-protein search becomes a reductase search. Hidden string
    params are internal switches whose defaults ARE correct (``document_type``
    is required with a ``gene`` default), so visibility is the discriminator.

    Numbers are excluded. WDK types its numeric bounds as ``string`` with
    ``isNumber: true`` (``dn_ds_ratio_lower``, ``MinPercentIsolateCalls``),
    and their initial value is what PlasmoDB pre-fills, not an example --
    treating them as free text asked five needless questions on one search.
    """
    return (
        info.param_kind == "string"
        and not info.is_number
        and info.is_visible
        and info.required
        and not info.allowed_values
        and not info.vocab_leaves
    )


def _scalar_default(info: ParameterInfo) -> str | None:
    """The param's default value, when it is a defaultable scalar/vocab kind.
    The degenerate-pair dedup is applied by the caller so it covers
    intent-resolved values too, not just defaults."""
    if not info.default_value or info.param_kind not in _SCALAR_DEFAULTABLE:
        return None
    if _is_free_text_query(info):
        return None
    return info.default_value


def _curated_multi_default(info: ParameterInfo) -> list[str] | None:
    """A multi-pick param's non-empty list default -- WDK's curated selection.

    ``text_fields`` defaults to all 25 searchable fields ("look everywhere").
    A slot-agnostic intent match would replace that with a single option, and
    the same query returns 0 against one field where it returns thousands
    against the full list. Params whose default is ``[]`` (the sample selectors)
    return ``None`` so intent matching still drives them.
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
    """Which vocabulary values same-vocab siblings have already taken.

    Params drawn from an identical option set (a ref-vs-comp contrast) must not
    land on the same value -- that compares a group to itself and returns zero
    rows. This tracks who took what, and whether they *chose* it (an explicit
    override) or merely *guessed* it (a default or an intent match), because the
    two rank differently when they collide.
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
        """Whether a sibling from the IDENTICAL vocabulary already took ``value``.

        A single-option vocabulary is exempt: there is no other value the sibling
        could take, so the "choice" this would surface has exactly one answer
        (the one just rejected) and the slot could never be closed.
        """
        if is_aggregation_param(f"{info.name} {info.display_name}"):
            # Aggregation selectors are not a contrast: applying "average" to
            # both the reference and the comparison group is the normal, correct
            # configuration, not a group compared against itself.
            return False
        if len(info.allowed_values or []) < _MIN_VOCAB_SIZE_FOR_DEGENERACY:
            return False
        signature = _vocab_signature(info)
        return signature is not None and value in self.taken.get(signature, set())

    def sole_remaining_option(
        self, info: ParameterInfo, taken_value: str
    ) -> str | None:
        """The single option left once siblings have taken theirs.

        Only applies when the colliding value was **pinned by an explicit
        override**: then the remainder is forced and picking it is deduction.
        When the sibling merely guessed, choosing the leftover would itself be a
        guess about contrast direction -- and getting ref-vs-comp backwards
        inverts the result -- so return ``None`` and ask the user.
        """
        signature = _vocab_signature(info)
        if signature is None or taken_value not in self.pinned.get(signature, set()):
            return None
        taken = self.taken.get(signature, set())
        remaining = [
            o.value for o in (info.allowed_values or []) if o.value not in taken
        ]
        return remaining[0] if len(remaining) == 1 else None

    def sole_remaining_after_authoritative(self, info: ParameterInfo) -> str | None:
        """The one option left once an authoritative sibling has taken its own.

        A reference slot is defined negatively -- it is whatever the comparator
        is contrasted against -- so it has no candidate of its own to offer. If
        exactly one option remains after an override or a comparator has
        claimed, that remainder is forced and deducing it beats asking.
        """
        signature = _vocab_signature(info)
        if signature is None or not self.pinned.get(signature):
            return None
        taken = self.taken.get(signature, set())
        remaining = [
            o.value for o in (info.allowed_values or []) if o.value not in taken
        ]
        return remaining[0] if len(remaining) == 1 else None

    def release_guess_holding(
        self, info: ParameterInfo, wanted: str, overrides: OverrideMap
    ) -> str | None:
        """Free ``wanted`` from a *guessed* claimant so this override can take it.

        An override is authoritative; a default or intent match is not. If the
        guess keeps the value, the override lands on top of it and the pair is
        degenerate. Returns the evicted param's name so the caller can unbind and
        re-resolve it (where the now-pinned value is excluded and the sole
        remaining option is deduced). Ordering alone cannot cover this: a param
        with ``vocab_depends_on`` is deferred to a later pass, by which point the
        guess is already bound.
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
    """A question for the user. Tree-box params keep their real values in
    ``vocab_leaves`` (``allowed_values`` is empty), so fall back to those rather
    than asking "choose a value" while offering none."""
    options = info.allowed_values or info.vocab_leaves
    return OpenSlot(
        param_name=info.name,
        question=f"Choose a value for {info.display_name}",
        options=[o.value for o in options][:_MAX_SLOT_OPTIONS],
    )


async def _resolve_nonfilter(
    info: ParameterInfo,
    intent: ParamIntent,
    embed: EmbedFn,
    overrides: OverrideMap,
    ledger: _VocabLedger,
) -> ParamValue | OpenSlot | None:
    """Resolve a non-filter param: Tier-0 override → Tier-1/2 intent → scalar
    default → Tier-3 slot. Records the chosen value against its vocabulary so a
    same-vocab sibling won't degenerately reuse it. ``None`` = optional + unset.

    Tier-0 outranks the degenerate-pair guard: an override is the user answering
    an open slot, so re-applying the guard to it would re-open the very slot they
    just closed and the turn could never proceed."""
    is_user_choice = info.name in overrides
    if not is_user_choice:
        curated = _curated_multi_default(info)
        if curated is not None:
            return param_value_for(info, curated)
    value = await _resolve_one(info, intent, embed, overrides)
    from_intent = value is not None
    if value is None:
        value = _scalar_default(info)
    if value is None and contrast_role(info) == "reference":
        value = ledger.sole_remaining_after_authoritative(info)
    claimed = _sole_claim(value)
    if (
        claimed is not None
        and not is_user_choice
        and ledger.duplicates_sibling(info, claimed)
    ):
        # The sibling already took this value. If a user pinned it and exactly
        # one option is left, that remainder is forced -- take it rather than
        # asking a question with a single possible answer.
        value = ledger.sole_remaining_option(info, claimed)
    resolved = _build_value(info, value)
    if resolved is not None and value is not None:
        signature = _vocab_signature(info)
        if signature is not None:
            # A comparator bound from the criterion's own subject is a grounded
            # choice, not a slot-agnostic guess, so it is authoritative enough
            # for the reference sibling to deduce the remaining option instead
            # of asking a question whose answer is already determined.
            # Grounded in what the user asked for -- an override, or a
            # comparator matched from the criterion's own subject. A scalar
            # DEFAULT is not grounded, so it must not license the reference
            # sibling to deduce a direction nobody chose.
            authoritative = is_user_choice or (
                from_intent and contrast_role(info) == "comparison"
            )
            claimed = _sole_claim(value)
            if claimed is not None:
                ledger.claim(signature, claimed, info.name, pinned=authoritative)
        return resolved
    if info.required:
        return _open_slot(info)
    return None


def _awaits_comparator(
    info: ParameterInfo, infos: list[ParameterInfo], resolved: set[str]
) -> bool:
    """Whether a reference slot must wait for its comparator sibling.

    The baseline is whatever the comparator is contrasted against, so resolving
    it first either grabs the subject (inverting the contrast) or strands it as
    an unanswerable slot that never revisits once the comparator lands.
    """
    if contrast_role(info) != "reference":
        return False
    # Pair on the NAME STEM. A vocabulary signature would not match while the
    # comparator still carries its pre-parent option set, and a bare role match
    # would couple unrelated pairs (the min/max/average operation selectors
    # would wait on the sample selectors and never resolve).
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
    """Unbind a guessed param holding the value this override wants, so the
    guess re-resolves against the now-claimed vocabulary."""
    if info.name not in overrides:
        return
    wanted = _sole_claim(_apply_override(info, overrides[info.name]))
    if wanted is None:
        return
    evicted = ledger.release_guess_holding(info, wanted, overrides)
    if evicted is None:
        return
    params.pop(evicted, None)
    context.pop(evicted, None)
    seen.discard(evicted)


def _resolution_rank(info: ParameterInfo, overrides: OverrideMap) -> tuple[int, int]:
    """Resolution order within a pass: authoritative values claim their
    vocabulary slot before anything guesses onto it.

    Overrides first (the user has spoken), then comparators (bound from the
    criterion's own subject), then everything else, and references LAST -- a
    reference is the baseline, defined by what the comparator did not take, so
    resolving it first would let it grab the subject and invert the contrast.
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
    """Whether to skip ``info`` until the walk re-fetches under a new context.

    Two reasons. Its vocabulary parent may be unresolved, so the param has no
    meaningful option set yet. Or the parent resolved *during this pass*, in
    which case ``infos`` -- fetched once, before that -- still carries the
    PRE-parent vocabulary. That stale option set is often narrower and sometimes
    a single value, so binding from it can silently take a value a sibling
    already holds. The next pass re-fetches and sees the real vocabulary.
    """
    depends_on = set(info.vocab_depends_on or [])
    if depends_on - context.keys():
        return True
    return bool(depends_on & resolved_this_pass)


async def resolve_params_with_intent(
    *,
    fetch_at: ParamFetcher,
    intent: ParamIntent,
    embed: EmbedFn,
    overrides: OverrideMap | None = None,
) -> ResolvedParams:
    """Walk the dependency DAG resolving each param Tier-0 (user override) →
    Tier-1 (auto) → Tier-2 (intent) → scalar default → Tier-3 (slot). Re-fetches
    after each pick so dependent params surface; bounded by ``_MAX_RESOLVE_DEPTH``."""
    overrides = overrides or {}
    context: dict[str, str] = {}
    params: dict[str, ParamValue] = {}
    open_slots: list[OpenSlot] = []
    unresolved: list[str] = []
    seen: set[str] = set()
    ledger = _VocabLedger()
    for _ in range(_MAX_RESOLVE_DEPTH):
        infos = await fetch_at(context)
        progressed = False
        # Overridden params first so an authoritative value claims its vocabulary
        # slot before a sibling guesses onto it. Ordering alone is not enough --
        # a dependent param (``vocab_depends_on``) is deferred to a later pass,
        # by which time the guess is already bound -- so _evict_guessed_claimer
        # also unwinds a guess that took an override's value.
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
            outcome: ParamValue | OpenSlot | None
            if info.param_kind == "filter":
                outcome = _resolve_filter_param(info, infos, overrides)
            else:
                outcome = await _resolve_nonfilter(
                    info, intent, embed, overrides, ledger
                )
            if isinstance(outcome, OpenSlot):
                open_slots.append(outcome)
                unresolved.append(info.name)
            elif outcome is not None:
                params[info.name] = outcome
                context[info.name] = to_wire(outcome)
                resolved_this_pass.add(info.name)
            seen.add(info.name)
            progressed = True
        if not progressed:
            break
    return ResolvedParams(
        params=params, open_slots=open_slots, unresolved_required=unresolved
    )


async def resolve_search_params(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    intent: ParamIntent,
    embed: EmbedFn,
    overrides: OverrideMap | None = None,
) -> ResolvedParams:
    return await resolve_params_with_intent(
        fetch_at=_wdk_fetch_at(site_id, record_type, search_name),
        intent=intent,
        embed=embed,
        overrides=overrides,
    )
