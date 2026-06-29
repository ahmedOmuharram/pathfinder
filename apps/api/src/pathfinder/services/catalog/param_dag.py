"""Deterministic resolution of a WDK search's parameter dependency DAG."""

from __future__ import annotations

import graphlib
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

from pydantic import (
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    field_validator,
)

from pathfinder.domain.parameters.values import (
    FilterTermClause,
    FilterValue,
    ParamValue,
    param_value_from_raw,
    to_wire,
)
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.domain.strategy.operational_spec import OpenSlot
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_formatting import (
    FilterFieldInfo,
    ParameterInfo,
    format_param_info_typed,
)
from pathfinder.services.catalog.param_intent import (
    EmbedFn,
    ParamIntent,
    map_intent_to_value,
    match_option,
)
from pathfinder.services.wdk import get_wdk_client

_SCALAR_DEFAULTABLE: frozenset[str] = frozenset(
    {"number", "string", "date", "timestamp", "single-pick-vocabulary"}
)
_MAX_RESOLVE_DEPTH = 6
_MAX_SLOT_OPTIONS = 20


def _vocab_signature(info: ParameterInfo) -> str | None:
    """A stable signature of a vocab param's option set, or ``None`` for params
    whose default can never form a degenerate pair (scalars / no vocab)."""
    values = info.allowed_values
    if not values:
        return None
    return "|".join(sorted(o.value for o in values))


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
        client = get_wdk_client(site_id)
        if context:
            resp = await client.get_search_details_with_params(
                record_type, search_name, context=context
            )
        else:
            resp = await client.get_search_details(record_type, search_name)
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


def _build_value(info: ParameterInfo, value: str | None) -> ParamValue | None:
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


def _apply_override(info: ParameterInfo, value: str) -> str:
    """A user-supplied value for an open slot. Match it to the param's
    vocabulary (so 'uninfected' resolves to the exact option, or a bare
    'Plasmodium vivax' snaps to the tree-box leaf 'Plasmodium vivax P01') when
    there is one; otherwise pass the value through for WDK to validate. Tree-box
    params carry their values in ``vocab_leaves`` rather than ``allowed_values``."""
    options = info.allowed_values or info.vocab_leaves
    if options:
        return match_option(options, value) or value
    return value


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
    except ValidationError:
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
    info: ParameterInfo, infos: list[ParameterInfo], overrides: dict[str, str]
) -> FilterValue | OpenSlot:
    """Resolve a filter param to a value, or surface an ``OpenSlot`` when it is
    an unspecified half of a ref/comp contrast pair (both halves defaulting to
    'all samples' is a degenerate all-vs-all contrast)."""
    override = overrides.get(info.name)
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
    overrides: dict[str, str],
) -> str | None:
    """Tier-0 user override (an answered open slot) → Tier-1 (single valid
    value) → Tier-2 (intent). Scalar-defaulting is decided by the walk so it
    can refuse a degenerate duplicate selection."""
    if info.name in overrides:
        return _apply_override(info, overrides[info.name])
    tier = classify_param(info)
    if isinstance(tier, AutoResolved):
        return tier.value
    return await map_intent_to_value(info, intent, embed=embed)


def _scalar_default(
    info: ParameterInfo, used_by_vocab: dict[str, set[str]]
) -> str | None:
    """The param's default — UNLESS it would duplicate a value already chosen
    for a sibling drawn from the identical vocabulary. Two same-vocab selectors
    defaulting to the same value form a degenerate pair (e.g. a DESeq
    ref-vs-comp contrast comparing a group to itself → zero results); leave the
    second one unresolved so it surfaces as a user choice instead."""
    if not info.default_value or info.param_kind not in _SCALAR_DEFAULTABLE:
        return None
    signature = _vocab_signature(info)
    if signature is not None and info.default_value in used_by_vocab.get(
        signature, set()
    ):
        return None
    return info.default_value


def _open_slot(info: ParameterInfo) -> OpenSlot:
    return OpenSlot(
        param_name=info.name,
        question=f"Choose a value for {info.display_name}",
        options=[o.value for o in (info.allowed_values or [])][:_MAX_SLOT_OPTIONS],
    )


async def _resolve_nonfilter(
    info: ParameterInfo,
    intent: ParamIntent,
    embed: EmbedFn,
    overrides: dict[str, str],
    used_by_vocab: dict[str, set[str]],
) -> ParamValue | OpenSlot | None:
    """Resolve a non-filter param: Tier-0 override → Tier-1/2 intent → scalar
    default → Tier-3 slot. Records the chosen value against its vocabulary so a
    same-vocab sibling won't degenerately reuse it. ``None`` = optional + unset."""
    value = await _resolve_one(info, intent, embed, overrides)
    if value is None:
        value = _scalar_default(info, used_by_vocab)
    resolved = _build_value(info, value)
    if resolved is not None and value is not None:
        signature = _vocab_signature(info)
        if signature is not None:
            used_by_vocab.setdefault(signature, set()).add(value)
        return resolved
    if info.required:
        return _open_slot(info)
    return None


async def resolve_params_with_intent(
    *,
    fetch_at: ParamFetcher,
    intent: ParamIntent,
    embed: EmbedFn,
    overrides: dict[str, str] | None = None,
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
    used_by_vocab: dict[str, set[str]] = {}
    for _ in range(_MAX_RESOLVE_DEPTH):
        infos = await fetch_at(context)
        progressed = False
        for info in infos:
            if info.name in seen or (set(info.vocab_depends_on or []) - context.keys()):
                continue
            outcome: ParamValue | OpenSlot | None
            if info.param_kind == "filter":
                outcome = _resolve_filter_param(info, infos, overrides)
            else:
                outcome = await _resolve_nonfilter(
                    info, intent, embed, overrides, used_by_vocab
                )
            if isinstance(outcome, OpenSlot):
                open_slots.append(outcome)
                unresolved.append(info.name)
            elif outcome is not None:
                params[info.name] = outcome
                context[info.name] = to_wire(outcome)
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
    overrides: dict[str, str] | None = None,
) -> ResolvedParams:
    return await resolve_params_with_intent(
        fetch_at=_wdk_fetch_at(site_id, record_type, search_name),
        intent=intent,
        embed=embed,
        overrides=overrides,
    )
