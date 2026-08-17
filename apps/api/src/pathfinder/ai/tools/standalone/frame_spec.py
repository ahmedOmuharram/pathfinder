from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator
from pydantic import ValidationError as PydanticValidationError
from pydantic_ai import ModelRetry, RunContext

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._catalog_models import (
    _resolve_record_type,
    ensure_search_registered,
    read_search_definition,
    register_search,
)
from pathfinder.ai.tools.standalone._validation_helpers import validation_model_retry
from pathfinder.domain.parameters.values import to_wire
from pathfinder.domain.parameters.wdk_vocab import (
    VocabOption,
    accession_matches,
    match_exact_option,
)
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OpenSlot,
    SpecStructure,
    StructureNode,
)
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_dag import (
    ParamFetcher,
    ResolvedParams,
    UnknownParameterError,
    resolve_params_with_intent,
    wdk_fetch_at,
)
from pathfinder.services.catalog.param_formatting import (
    ParameterInfo,
    format_param_info_typed,
)
from pathfinder.services.catalog.param_intent import ParamIntent
from pathfinder.services.catalog.param_sheet import SheetEntry, build_sheet
from pathfinder.services.catalog.param_validation import validate_parameters
from pathfinder.services.catalog.validation_callbacks import make_validation_callbacks
from pathfinder.services.wdk import WDKSearch

CriterionRole = Literal["seed", "filter", "transform", "exclude"]


class _Proposal(BaseModel):
    """One proposed value as the model may type it: a string, a number, a list,
    a JSON-encoded list, or null."""

    model_config = ConfigDict(coerce_numbers_to_str=True)
    value: str | list[str] | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _json_word(cls, v: object) -> object:
        """A boolean is its JSON word, so a yes/no vocabulary answers it."""
        if isinstance(v, bool):
            return "true" if v else "false"
        return v

    @field_validator("value", mode="before")
    @classmethod
    def _json_list(cls, v: object) -> object:
        if not isinstance(v, str) or not v.startswith("["):
            return v
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError:
            # Bracketed text that is not a JSON list is a literal value.
            return v
        return [str(x) for x in parsed] if isinstance(parsed, list) else v


def _proposed(name: str, value: object) -> str | list[str] | None:
    try:
        return _Proposal.model_validate({"value": value}).value
    except PydanticValidationError as exc:
        message = f"{name}: {exc.errors()[0]['msg']}"
        raise ValueError(message) from exc


def coerce_proposals(raw: object) -> object:
    """Reads each proposed value in the form the model wrote it. A non-mapping
    passes through so Pydantic reports the type error."""
    if not isinstance(raw, dict):
        return raw
    return {str(name): _proposed(str(name), value) for name, value in raw.items()}


ParamProposals = Annotated[
    dict[str, str | list[str] | None], BeforeValidator(coerce_proposals)
]


class SetCriterionResult(CamelModel):
    """Result of binding a criterion to a WDK search and resolving its params."""

    criterion_id: str
    search_name: str
    # Every visible parameter name mapped to null, in sheet order. Declared
    # before `decide` so the object to copy is read before the vocabularies.
    params_template: dict[str, None] = Field(default_factory=dict)
    # The parameter sheet, returned when the call proposes no params. Nothing is
    # recorded then: it is the input the next call proposes values from.
    decide: list[SheetEntry] = Field(default_factory=list)
    # Name -> bound value, not just the names. A binding can be syntactically
    # "resolved" and semantically wrong (WDK ships `*reductase` as GenesByText's
    # example default), and reporting only names makes that invisible to the
    # model, the ledger, and the user until the step silently returns zero rows.
    resolved_params: dict[str, str] = Field(default_factory=dict)
    # Params the search defaulted. State these to the user with their values.
    defaulted_params: list[str] = Field(default_factory=list)
    open_slots: list[OpenSlot] = Field(default_factory=list)
    # Dependent params whose vocabulary changed once the parents were bound.
    # A non-empty list means nothing was recorded; decide these and re-call.
    redecide: list[SheetEntry] = Field(default_factory=list)


class SetStructureResult(CamelModel):
    """Result of folding the bound criteria into the strategy structure."""

    criteria_combined: int


class DropCriterionResult(CamelModel):
    """Result of dropping a criterion from the spec."""

    criterion_id: str
    reason: str


async def _record_type(ctx: RunContext[AgentDeps], search_name: str) -> str:
    """The record type that owns the search, resolved once for the whole call.

    The strategy graph's record type answers whenever the session holds a graph,
    whatever search is named; the catalog resolves the name only without one.
    """
    graph = ctx.deps.strategy_session.get_graph(None)
    return await _resolve_record_type(
        ctx.deps.site_id,
        search_name,
        graph.record_type if graph is not None else None,
    )


# Enough nearest entries to recognise the one meant, few enough to read.
_NEAREST_ENTRIES = 5


@dataclass(frozen=True)
class _CriterionCall:
    """The one call's identity, carried through the checks it drives."""

    criterion_id: str
    search_name: str
    text: str
    params: ParamProposals


def _memoized_fetch(site_id: str, record_type: str, search_name: str) -> ParamFetcher:
    """Reads the search once per parameter context for the whole call.

    The name check, the DAG walk and the dependent re-read all want the same
    expandParams payload.
    """
    fetch_at = wdk_fetch_at(site_id, record_type, search_name)
    read: dict[tuple[tuple[str, str], ...], list[ParameterInfo]] = {}

    async def memoized(context: dict[str, str]) -> list[ParameterInfo]:
        key = tuple(sorted(context.items()))
        if key not in read:
            read[key] = await fetch_at(context)
        return read[key]

    return memoized


def _values_of(proposal: str | list[str] | None) -> list[str]:
    if proposal is None:
        return []
    return proposal if isinstance(proposal, list) else [proposal]


def _nearest(pool: list[str], value: str) -> list[str]:
    """The entries closest to the value, the ones it starts first.

    A value that starts an entry is the accession or the stem of that entry.
    Character similarity alone ranks such an entry below unrelated ones.
    """
    key = value.casefold()
    started = [entry for entry in pool if entry.casefold().startswith(key)]
    room = _NEAREST_ENTRIES - len(started)
    if room <= 0:
        return started[:_NEAREST_ENTRIES]
    taken = set(started)
    rest = [entry for entry in pool if entry not in taken]
    return started + difflib.get_close_matches(value, rest, n=room, cutoff=0.0)


def _refuse_unknown_names(call: _CriterionCall, infos: list[ParameterInfo]) -> None:
    """A proposal names a visible parameter of the search.

    A null proposal is dropped before the DAG's own name check, so a misspelt
    name paired with a null would otherwise set nothing and say nothing.
    """
    visible = sorted(i.name for i in infos if i.is_visible)
    unknown = sorted(set(call.params) - set(visible))
    if unknown:
        msg = (
            f"No such parameter(s) on {call.search_name}: {unknown}. Nearest: "
            f"{_nearest(visible, unknown[0])}. The valid names are listed above; "
            f"do not request the sheet again. Valid names: {visible}."
        )
        raise ModelRetry(msg)


def _refuse_undecided(call: _CriterionCall, infos: list[ParameterInfo]) -> None:
    """Every visible required parameter needs a value or a null."""
    required = {i.name for i in infos if i.is_visible and i.required}
    undecided = sorted(required - set(call.params))
    if undecided:
        msg = (
            f"Decide every visible required parameter of {call.search_name}: missing "
            f"{undecided}. Pass a value from the sheet, or null for the default. "
            f"The valid names are listed above; do not request the sheet again."
        )
        raise ModelRetry(msg)


def _refuse_unmatched_value(
    call: _CriterionCall, info: ParameterInfo, options: list[VocabOption]
) -> None:
    """A proposed vocabulary value is one of the entries, not a substring."""
    unmatched = [
        value
        for value in _values_of(call.params.get(info.name))
        if match_exact_option(options, value) is None
    ]
    if not unmatched:
        return
    shared = accession_matches(options, unmatched[0])
    if len(shared) > 1:
        msg = (
            f"{info.name} on {call.search_name}: {len(shared)} entries share the "
            f"accession {unmatched[0]!r}; copy the full value of the one you mean: "
            f"{shared[:_NEAREST_ENTRIES]}."
        )
        raise ModelRetry(msg)
    pool = [o.value for o in options] + [o.display for o in options if o.display]
    msg = (
        f"{info.name} on {call.search_name} has no entry matching {unmatched}. Copy "
        f"a value or a label from the vocabulary exactly; a substring names a "
        f"different entry. Nearest entries: "
        f"{_nearest(list(dict.fromkeys(pool)), unmatched[0])}."
    )
    raise ModelRetry(msg)


def _refuse_unmatched_values(call: _CriterionCall, infos: list[ParameterInfo]) -> None:
    """Checks every proposal the sheet's own vocabulary can answer.

    A dependent parameter is skipped here: the sheet showed its vocabulary under
    the search defaults, and ``_reconcile_dependents`` checks it against the one
    the bound parents produce. A filter parameter takes a facet expression, not
    a vocabulary entry.
    """
    for info in infos:
        options = info.vocabulary()
        skip = info.vocab_depends_on or info.param_kind == "filter" or not options
        if info.name in call.params and not skip:
            _refuse_unmatched_value(call, info, options)


def _decided_here(info: ParameterInfo, params: ParamProposals) -> bool:
    """The proposal for this param names an entry of the vocabulary shown here."""
    if info.name not in params:
        return False
    values = _values_of(params[info.name])
    options = info.vocabulary()
    return bool(values) and all(
        match_exact_option(options, value) is not None for value in values
    )


async def _reconcile_dependents(
    fetch_at: ParamFetcher,
    infos: list[ParameterInfo],
    resolved: ResolvedParams,
    call: _CriterionCall,
    state: AgentToolState,
) -> list[SheetEntry]:
    """Visible dependent params to hand back with the vocabulary the parents produce.

    The sheet was read under the search defaults, so a proposal made from it does
    not decide the vocabulary the bound parents produce. A param already handed
    back for this criterion is decided by whatever the re-call says, so it is
    validated against the fresh vocabulary instead of asked again.
    """
    on_the_sheet = {
        info.name: {option.value for option in info.vocabulary()}
        for info in infos
        if info.is_visible and info.vocab_depends_on
    }
    if not on_the_sheet:
        return []
    context = {name: to_wire(value) for name, value in resolved.params.items()}
    stale: list[ParameterInfo] = []
    for info in await fetch_at(context):
        if info.name not in on_the_sheet:
            continue
        options = info.vocabulary()
        changed = {option.value for option in options} != on_the_sheet[info.name]
        asked = state.was_redecided(call.criterion_id, call.search_name, info.name)
        if changed and not asked and not _decided_here(info, call.params):
            stale.append(info)
        elif options and info.param_kind != "filter":
            _refuse_unmatched_value(call, info, options)
    for info in stale:
        state.mark_redecided(call.criterion_id, call.search_name, info.name)
    return build_sheet(stale, query=call.text)


_RE_SHEET_NOTE = (
    "vocabulary shown in the first sheet; use get_parameter_options(search_name, "
    "parameter_id, query=...) for an entry you no longer see"
)


def _sheet_for(
    state: AgentToolState, criterion_id: str, search_name: str, definition: WDKSearch
) -> list[SheetEntry]:
    """The parameter sheet for one criterion, without repeating a vocabulary.

    The second sheet for the same criterion and search carries every parameter
    but no vocabulary, which the model already holds.
    """
    entries = build_sheet(
        format_param_info_typed(definition.parameters or []),
        query=state.operational_spec_draft.goal,
    )
    if not state.was_sheet_shown(criterion_id, search_name):
        state.mark_sheet_shown(criterion_id, search_name)
        return entries
    return [
        entry.model_copy(update={"vocabulary": [], "vocabulary_note": _RE_SHEET_NOTE})
        for entry in entries
    ]


async def set_criterion(
    ctx: RunContext[AgentDeps],
    *,
    criterion_id: str,
    text: str,
    search_name: str,
    role: CriterionRole = "filter",
    params: ParamProposals | None = None,
) -> SetCriterionResult:
    """Bind a criterion to a WDK search, in two calls.

    Call this ONCE with no ``params`` to receive ``decide``, the PARAMETER
    SHEET: every visible parameter of the search with its type, help, default,
    dependency, and its vocabulary -- whole, or the 200 entries most relevant to
    the request. Nothing is recorded by that call. The result's
    ``params_template`` is the exact ``params`` object to send back: copy it and
    replace each null with a value or leave null; do not rename keys. Then call
    it AGAIN with that ``params`` object.

    A value must be copied from the sheet's vocabulary when the parameter has
    one (a tree parent term selects its children); a number or free text is the
    literal the request states; a filter parameter takes "<facet>=<v1>,<v2>".
    ``null`` means the request does not determine it: the search default applies
    and is reported in ``defaulted_params``, or the parameter becomes an open
    slot when there is no default. Do not pass null for a numeric parameter when
    ``text`` states its value; pass the stated number. Never invent a value; a
    name that is not on the sheet comes back as a retry listing the real ones,
    and a missing vocabulary entry means the search cannot realize the
    criterion, or the value is beyond a shortlisted vocabulary (use
    ``get_parameter_options(query=...)``).

    ``redecide`` lists dependent parameters whose vocabulary changed once the
    parents were bound, each with that fresh vocabulary; nothing is recorded
    then. Re-call with the same ``params`` and either a value from the fresh
    vocabulary or the same null for each listed parameter, and it closes. Re-call
    the same way once the user answers an open slot."""
    state = ctx.deps.agent_state
    record_type = await _record_type(ctx, search_name)
    if params is None:
        definition = await read_search_definition(
            ctx.deps.site_id, record_type, search_name
        )
        register_search(state, definition, record_type)
        entries = _sheet_for(state, criterion_id, search_name, definition)
        return SetCriterionResult(
            criterion_id=criterion_id,
            search_name=search_name,
            params_template={entry.name: None for entry in entries},
            decide=entries,
        )
    await ensure_search_registered(state, ctx.deps.site_id, record_type, search_name)
    fetch_at = _memoized_fetch(ctx.deps.site_id, record_type, search_name)
    infos = await fetch_at({})
    search = SearchContext(ctx.deps.site_id, record_type, search_name)
    call = _CriterionCall(
        criterion_id=criterion_id, search_name=search_name, text=text, params=params
    )
    _refuse_unknown_names(call, infos)
    _refuse_undecided(call, infos)
    _refuse_unmatched_values(call, infos)
    # A null proposal states no value, so it leaves the param to resolution.
    overrides = {name: value for name, value in params.items() if value is not None}
    try:
        resolved = await resolve_params_with_intent(
            fetch_at=fetch_at,
            intent=ParamIntent(text=text),
            overrides=overrides,
        )
    except UnknownParameterError as exc:
        msg = (
            f"{exc.detail} The valid names are listed above; do not request the "
            f"sheet again."
        )
        raise ModelRetry(msg) from exc
    if resolved.unread:
        msg = (
            f"The criterion states a quantity and {resolved.unread} was left null. "
            f"Pass the stated value, or say in the criterion text why the default "
            f"is right."
        )
        raise ModelRetry(msg)
    redecide = await _reconcile_dependents(fetch_at, infos, resolved, call, state)
    if redecide:
        return SetCriterionResult(
            criterion_id=criterion_id, search_name=search_name, redecide=redecide
        )
    # A complete spec is validated here so a bad value returns a did-you-mean
    # retry. An open slot means a required param is still unresolved, which
    # WDK reports as missing.
    defaulted = resolved.defaulted()
    if not resolved.open_slots:
        try:
            validated = await validate_parameters(
                search,
                parameters=dict(resolved.params),
                callbacks=make_validation_callbacks(ctx.deps.site_id),
            )
        except ValidationError as exc:
            raise validation_model_retry(
                exc, recordType=record_type, searchName=search_name
            ) from exc
        # WDK renders the spec it would run, so it reports which values are its
        # own. That report is about the search being built and outranks the
        # local reading of the request.
        defaulted = sorted(set(defaulted) | set(validated.substituted))
    open_params = [
        OpenSlot(
            criterion_id=criterion_id,
            param_name=slot.param_name,
            question=slot.question,
            options=slot.options,
        )
        for slot in resolved.open_slots
    ]
    state.frame_set_criterion(
        Criterion(
            id=criterion_id,
            text=text,
            search_name=search_name,
            role=role,
            resolved_params=resolved.params,
            defaulted_params=defaulted,
            open_params=open_params,
        )
    )
    return SetCriterionResult(
        criterion_id=criterion_id,
        search_name=search_name,
        resolved_params={
            name: to_wire(value) for name, value in resolved.params.items()
        },
        defaulted_params=defaulted,
        open_slots=open_params,
    )


def _count_criteria(node: StructureNode) -> int:
    own = 1 if node.criterion_id else 0
    return own + sum(_count_criteria(child) for child in node.inputs)


async def set_structure(
    ctx: RunContext[AgentDeps],
    *,
    root: StructureNode,
) -> SetStructureResult:
    """Set the strategy tree from the bound criteria.

    ``root`` is a tree, not a list, because the shape carries meaning. Each
    node is one of:

    - ``{"kind": "leaf", "criterionId": "<id>"}`` -- one bound criterion.
    - ``{"kind": "combine", "operator": "INTERSECT" | "UNION" | "MINUS",
      "inputs": [<left>, <right>]}`` -- boolean-combine two subtrees.
    - ``{"kind": "transform", "criterionId": "<id>", "inputs": [<subtree>]}``
      -- a search that MAPS the subtree's genes rather than combining with
      them (e.g. ``GenesByOrthologs`` returning orthologs in another
      organism). It is wired to that input, never run standalone.

    Nest freely. When a property has several alternative evidence sources,
    UNION them into their own branch and INTERSECT that branch with the
    others -- do not flatten it into a chain, which asks a different
    question. WDK step trees carry a primary and a secondary input, so a
    branch on either side is representable.
    """
    ctx.deps.agent_state.frame_set_structure(SpecStructure(root=root))
    return SetStructureResult(criteria_combined=_count_criteria(root))


def drop_criterion(
    ctx: RunContext[AgentDeps], *, criterion_id: str, reason: str
) -> DropCriterionResult:
    """Remove a criterion (by the ``criterion_id`` you set in ``set_criterion``)
    from the spec, e.g. when its WDK search is unavailable or has no realizable
    binding. The criterion and its open params are removed (so it no longer
    blocks the build) and recorded in ``dropped`` to surface to the user."""
    dropped = ctx.deps.agent_state.frame_drop_criterion(criterion_id, reason)
    if not dropped:
        ids = [c.id for c in ctx.deps.agent_state.operational_spec_draft.criteria]
        msg = (
            f"No criterion with id {criterion_id!r} to drop. Use the exact "
            f"criterion_id from set_criterion. Current criteria: {ids}."
        )
        raise ModelRetry(msg)
    return DropCriterionResult(criterion_id=criterion_id, reason=reason)
