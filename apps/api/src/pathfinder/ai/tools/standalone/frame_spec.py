from __future__ import annotations

from typing import Literal

from pydantic_ai import ModelRetry, RunContext

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.memory.embedding import embed_text
from pathfinder.ai.tools.standalone._validation_helpers import validation_model_retry
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OpenSlot,
    SpecStructure,
    StructureNode,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.platform.errors import ValidationError
from pathfinder.services.catalog.param_dag import resolve_search_params
from pathfinder.services.catalog.param_intent import ParamIntent
from pathfinder.services.catalog.param_validation import validate_parameters
from pathfinder.services.catalog.validation_callbacks import make_validation_callbacks

CriterionRole = Literal["seed", "filter", "transform", "exclude"]


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
    param_overrides: dict[str, str] | None = None,
) -> str:
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
        site_id=ctx.deps.site_id,
        record_type=record_type,
        search_name=search_name,
        intent=intent,
        embed=embed_text,
        overrides=param_overrides,
    )
    # Validate the resolved values against WDK NOW (not at build time) — but only
    # once the spec is complete: an open slot means a required param is still
    # unresolved, which would falsely trip the "missing required" check. A value
    # error (e.g. an invalid vocab/multi-pick value) surfaces here as a
    # did-you-mean retry instead of failing the build and looping recovery.
    if not resolved.open_slots:
        try:
            await validate_parameters(
                SearchContext(ctx.deps.site_id, record_type, search_name),
                parameters=dict(resolved.params),
                callbacks=make_validation_callbacks(ctx.deps.site_id),
            )
        except ValidationError as exc:
            raise validation_model_retry(
                exc, recordType=record_type, searchName=search_name
            ) from exc
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
            open_params=open_params,
        )
    )
    note = (
        f"bound {criterion_id} -> {search_name}: {len(resolved.params)} params resolved"
    )
    if open_params:
        note += f"; needs user input: {[s.param_name for s in open_params]}"
    return note


async def set_structure(
    ctx: RunContext[AgentDeps],
    *,
    criterion_ids: list[str],
    operators: list[str],
) -> str:
    """Combine the bound criteria into the strategy tree (left-fold).
    ``operators`` has ``len(criterion_ids) - 1`` entries, each INTERSECT | UNION
    | MINUS | TRANSFORM. Use TRANSFORM when the next criterion's search MAPS the
    accumulated result rather than boolean-combining with it — e.g. an ortholog
    search (GenesByOrthologs) that takes the prior step's genes as its input and
    returns their orthologs. A TRANSFORM step is wired to that input, not run
    standalone."""
    if not criterion_ids:
        return "no criteria to combine"
    valid = {o.value for o in CombineOp}
    nodes = [StructureNode(kind="leaf", criterion_id=cid) for cid in criterion_ids]
    root = nodes[0]
    for i, node in enumerate(nodes[1:]):
        raw = operators[i].upper() if i < len(operators) else "INTERSECT"
        if raw == "TRANSFORM":
            root = StructureNode(
                kind="transform", criterion_id=node.criterion_id, inputs=[root]
            )
            continue
        op = CombineOp(raw if raw in valid else "INTERSECT")
        root = StructureNode(kind="combine", operator=op, inputs=[root, node])
    ctx.deps.agent_state.frame_set_structure(SpecStructure(root=root))
    return f"structure set over {len(criterion_ids)} criteria"


def drop_criterion(
    ctx: RunContext[AgentDeps], *, criterion_id: str, reason: str
) -> str:
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
    return f"dropped criterion: {criterion_id} ({reason})"
