from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_ai import ModelRetry, RunContext

from pathfinder.ai.agents.vocab_resolver import (
    resolve_free_value,
    resolve_vocabulary_value,
)
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.memory.embedding import embed_text
from pathfinder.ai.tools.standalone._validation_helpers import validation_model_retry
from pathfinder.domain.parameters.values import to_wire
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OpenSlot,
    SpecStructure,
    StructureNode,
)
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_dag import resolve_search_params
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import ParamIntent, ValueResolvers
from pathfinder.services.catalog.param_validation import validate_parameters
from pathfinder.services.catalog.validation_callbacks import make_validation_callbacks

CriterionRole = Literal["seed", "filter", "transform", "exclude"]


class SetCriterionResult(CamelModel):
    """Result of binding a criterion to a WDK search and resolving its params."""

    criterion_id: str
    search_name: str
    # Name -> bound value, not just the names. A binding can be syntactically
    # "resolved" and semantically wrong (WDK ships `*reductase` as GenesByText's
    # example default), and reporting only names makes that invisible to the
    # model, the ledger, and the user until the step silently returns zero rows.
    resolved_params: dict[str, str] = Field(default_factory=dict)
    # Params the search defaulted. State these to the user with their values.
    defaulted_params: list[str] = Field(default_factory=list)
    open_slots: list[OpenSlot] = Field(default_factory=list)


class SetStructureResult(CamelModel):
    """Result of folding the bound criteria into the strategy structure."""

    criteria_combined: int


class DropCriterionResult(CamelModel):
    """Result of dropping a criterion from the spec."""

    criterion_id: str
    reason: str


async def pick_from_vocabulary(
    text: str, pi: ParameterInfo, candidates: list[VocabOption]
) -> str | list[str] | None:
    """Adapt the seam's ``ParameterInfo`` to the resolver's arguments."""
    return await resolve_vocabulary_value(
        text,
        param_name=pi.name,
        param_help=pi.help,
        accepts_many=pi.param_kind == "multi-pick-vocabulary",
        candidates=candidates,
    )


async def read_free_value(text: str, pi: ParameterInfo) -> str | None:
    """Adapt the seam's ``ParameterInfo`` to the resolver's arguments."""
    return await resolve_free_value(
        text,
        param_name=pi.name,
        param_type=pi.type,
        help_text=pi.help,
    )


def _record_type(ctx: RunContext[AgentDeps]) -> str:
    graph = ctx.deps.strategy_session.get_graph(None)
    return (graph.record_type if graph is not None else None) or "transcript"


async def set_criterion(
    ctx: RunContext[AgentDeps],
    *,
    criterion_id: str,
    text: str,
    search_name: str,
    role: CriterionRole = "filter",
    organism_scope: str | None = None,
    direction: Literal["up", "down"] | None = None,
    param_overrides: dict[str, str | list[str]] | None = None,
) -> SetCriterionResult:
    """Bind a criterion to a real WDK search and auto-resolve its params
    (Tier-1 auto + Tier-2 intent). Required params that stay unresolved become
    open slots for the user. ``organism_scope`` e.g. "Plasmodium falciparum";
    ``direction`` for fold-change searches. When the user has answered an open
    slot, RE-CALL this with ``param_overrides`` mapping the exact open-slot
    param name(s) to the chosen value(s) (e.g.
    ``{"samples_de_comp_generic_deseq": "gametocyte"}``) — those values take
    priority over auto-resolution and close the slot."""
    intent = ParamIntent(
        organism_scope=organism_scope, text=text, direction_hint=direction
    )
    record_type = _record_type(ctx)
    resolved = await resolve_search_params(
        SearchContext(ctx.deps.site_id, record_type, search_name),
        intent=intent,
        embed=embed_text,
        resolvers=ValueResolvers(vocab=pick_from_vocabulary, free=read_free_value),
        overrides=param_overrides,
    )
    # A complete spec is validated here so a bad value returns a did-you-mean
    # retry. An open slot means a required param is still unresolved, which
    # WDK reports as missing.
    defaulted = resolved.defaulted()
    if not resolved.open_slots:
        try:
            validated = await validate_parameters(
                SearchContext(ctx.deps.site_id, record_type, search_name),
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
    ctx.deps.agent_state.frame_set_criterion(
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
    from the spec — e.g. when its WDK search is unavailable or has no realizable
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
