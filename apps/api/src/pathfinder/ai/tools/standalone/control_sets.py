"""Lead tools for sourcing + persisting control gene sets (Phase 2b).

A scored experiment needs positive/negative control gene lists. These tools
let the Lead validate user-provided IDs against WDK and persist a ControlSet,
plus list and pull from existing control sets / saved gene sets / strategies.
"""

from __future__ import annotations

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.standalone._id_arguments import parse_id_argument
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.control_sets import ControlSetService, NewControlSet
from pathfinder.services.experiment.control_sourcing import (
    control_ids_from_saved_gene_set,
    control_ids_from_strategy,
    validate_control_ids,
)


class BuiltControlSet(CamelModel):
    control_set_id: str
    name: str
    positive_count: int
    negative_count: int
    unresolved_positive: list[str]
    unresolved_negative: list[str]


async def build_control_set(
    ctx: RunContext[LeadDeps],
    name: str,
    positive_ids: list[str],
    negative_ids: list[str] | None = None,
    record_type: str = "transcript",
) -> BuiltControlSet:
    """Validate gene IDs against WDK and save them as a reusable control set
    for scored experiments. Pass the positive controls (genes that SHOULD be
    found) and optional negative controls (genes that should NOT). IDs that
    WDK doesn't recognize are dropped and reported back so you can tell the
    user about typos. Requires at least one recognized positive control.
    """
    runtime = ctx.deps.runtime

    pos = await validate_control_ids(
        runtime.site_id, positive_ids, record_type=record_type
    )
    neg = await validate_control_ids(
        runtime.site_id, negative_ids or [], record_type=record_type
    )
    if not pos.valid_ids:
        msg = (
            "No positive control IDs were recognized by WDK "
            f"(unresolved: {pos.unresolved_ids}). Check the IDs and retry."
        )
        raise ModelRetry(msg)

    async with runtime.db_session_factory() as session:
        created = await ControlSetService(session).create(
            NewControlSet(
                name=name,
                site_id=runtime.site_id,
                record_type=record_type,
                positive_ids=pos.valid_ids,
                negative_ids=neg.valid_ids,
                source="chat",
            ),
            user_id=runtime.user_id,
        )
        await session.commit()

    return BuiltControlSet(
        control_set_id=created.id,
        name=created.name,
        positive_count=len(pos.valid_ids),
        negative_count=len(neg.valid_ids),
        unresolved_positive=pos.unresolved_ids,
        unresolved_negative=neg.unresolved_ids,
    )


class ControlSetSummary(CamelModel):
    control_set_id: str
    name: str
    positive_count: int
    negative_count: int


async def list_control_sets(
    ctx: RunContext[LeadDeps],
) -> list[ControlSetSummary]:
    """List the user's saved control sets for this site, so you can offer them
    as the scoring basis instead of asking for new IDs."""
    runtime = ctx.deps.runtime
    async with runtime.db_session_factory() as session:
        sets = await ControlSetService(session).list_for_site(
            site_id=runtime.site_id, user_id=runtime.user_id, tags=None
        )
    return [
        ControlSetSummary(
            control_set_id=cs.id,
            name=cs.name,
            positive_count=len(cs.positive_ids),
            negative_count=len(cs.negative_ids),
        )
        for cs in sets
    ]


async def import_control_ids_from_gene_set(
    ctx: RunContext[LeadDeps],
    gene_set_id: str,
) -> list[str]:
    """Return the gene IDs of a saved workbench gene set, to use as controls."""
    return await control_ids_from_saved_gene_set(ctx.deps.runtime.user_id, gene_set_id)


async def import_control_ids_from_strategy(
    ctx: RunContext[LeadDeps],
    strategy_id: str,
) -> list[str]:
    """Return the result gene IDs of another strategy (a conversation id), to
    use as positive or negative controls."""
    runtime = ctx.deps.runtime
    parsed = parse_id_argument(
        strategy_id, argument="strategy_id", names="conversation"
    )
    async with runtime.db_session_factory() as session:
        result = await control_ids_from_strategy(
            session,
            parsed,
            runtime.site_id,
            runtime.user_id,
        )
    if result.error:
        msg = f"Could not import from strategy {strategy_id}: {result.error}"
        raise ModelRetry(msg)
    return result.gene_ids
