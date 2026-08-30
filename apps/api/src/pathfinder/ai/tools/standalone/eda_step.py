"""Export the open EDA analysis into the researcher's strategy as a WDK step."""

from __future__ import annotations

from typing import Literal

from assistant_core.graph.tool_summary import with_summary
from assistant_core.platform.pydantic_base import CamelModel
from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolReturn
from pydantic_ai.ui.vercel_ai.response_types import DataChunk
from shared_py.stream_parts.eda import EdaEffectDirection

from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.standalone._stream_parts import (
    graph_snapshot_chunk,
    strategy_link_chunk,
)
from pathfinder.ai.tools.standalone._validation_helpers import get_graph
from pathfinder.domain.strategy.operations import AddLeafOp
from pathfinder.domain.strategy.operations.types import (
    AttachIntoSlot,
    AttachNewRoot,
    AttachPoint,
)
from pathfinder.platform.errors import ValidationError
from pathfinder.services.eda.binding import (
    ConversationAnalysisView,
    bound_conversation_analysis,
    read_analysis,
)
from pathfinder.services.eda.compute import NoComputationError, VolcanoThresholds
from pathfinder.services.eda.steps import eda_step_node
from pathfinder.services.strategies.commit import apply_operations_and_commit
from pathfinder.services.strategies.context import StrategyMutationContext


class EdaStepCreated(CamelModel):
    """What the researcher's strategy now holds, and what to say about it."""

    search_name: str
    step_id: str
    dataset_id: str
    analysis_id: str
    is_compute_backed: bool = False
    effect_size_threshold: float | None = None
    significance_threshold: float | None = None
    effect_direction: EdaEffectDirection | None = None
    wdk_strategy_id: int | None = None
    wdk_url: str | None = None
    failed_step_ids: list[str] = Field(default_factory=list)
    guidance: str = ""


def _thresholds(
    effect_size_threshold: float | None,
    significance_threshold: float | None,
    effect_direction: EdaEffectDirection,
) -> VolcanoThresholds | None:
    """The volcano cut this call names, or None for the subset export."""
    if effect_size_threshold is None or significance_threshold is None:
        return None
    return VolcanoThresholds(
        effect_size_threshold=effect_size_threshold,
        significance_threshold=significance_threshold,
        effect_direction=effect_direction,
    )


async def bound_analysis(
    ctx: RunContext[LeadDeps],
) -> ConversationAnalysisView | None:
    """The analysis this conversation has open, or None."""
    return await bound_conversation_analysis(
        conversation_id=ctx.deps.state.conversation_id
    )


def _strategy_context(ctx: RunContext[LeadDeps]) -> StrategyMutationContext:
    runtime = ctx.deps.runtime
    return StrategyMutationContext(
        site_id=runtime.site_id,
        strategy_session=runtime.strategy_session,
        conversation_id=ctx.deps.state.conversation_id,
        db_session_factory=runtime.db_session_factory,
    )


def _checked_thresholds(
    effect_size_threshold: float | None,
    significance_threshold: float | None,
) -> None:
    """Both thresholds or neither. The bridge plugin requires both keys."""
    if effect_size_threshold is not None and significance_threshold is None:
        msg = (
            "A volcano export needs significanceThreshold as well as "
            "effectSizeThreshold. Send both, or send neither to export the "
            "whole subset."
        )
        raise ModelRetry(msg)
    if significance_threshold is not None and effect_size_threshold is None:
        msg = (
            "A volcano export needs effectSizeThreshold as well as "
            "significanceThreshold. Send both, or send neither to export the "
            "whole subset."
        )
        raise ModelRetry(msg)


def _attach_point(
    attach_to_step_id: str | None,
    slot: Literal["primary", "secondary"] | None,
) -> AttachPoint:
    if attach_to_step_id is None and slot is None:
        return AttachNewRoot()
    if attach_to_step_id is None:
        msg = (
            f"slot={slot!r} names an input of a combine step, so it needs "
            f"attachToStepId. Leave both unset to add the step as a new root."
        )
        raise ModelRetry(msg)
    if slot is None:
        msg = (
            f"attachToStepId={attach_to_step_id!r} needs a slot: 'primary' or "
            f"'secondary' names which input of that combine to fill."
        )
        raise ModelRetry(msg)
    return AttachIntoSlot(target_step_id=attach_to_step_id, slot=slot)


def _guidance(wdk_strategy_id: int | None, *, is_compute_backed: bool) -> str:
    kind = "the volcano's retained genes" if is_compute_backed else "the subset"
    strategy = (
        f"It is WDK strategy {wdk_strategy_id}."
        if wdk_strategy_id is not None
        else "WDK has not accepted it yet."
    )
    return (
        f"The step holds {kind} and behaves like any other step from now on: "
        f"combine it, transform it or save it. {strategy}"
    )


async def create_eda_step(
    ctx: RunContext[LeadDeps],
    *,
    search_name: str | None = None,
    attach_to_step_id: str | None = None,
    slot: Literal["primary", "secondary"] | None = None,
    effect_size_threshold: float | None = None,
    significance_threshold: float | None = None,
    effect_direction: EdaEffectDirection = "upAndDown",
) -> ToolReturn[EdaStepCreated]:
    """Export the open EDA analysis into the researcher's strategy as a step.

    The step is an ordinary WDK step from then on: it combines, transforms,
    nests and saves like any other, and it appears in the strategy graph the
    researcher is looking at.

    Two exports, and the arguments decide which:

    - The SUBSET's genes: call with no thresholds. Every gene in the filtered
      subset becomes a step.
    - The genes passing a VOLCANO's thresholds: pass ``effectSizeThreshold``
      AND ``significanceThreshold``. The compute must already be complete -
      call run_eda_compute first and read its summary, so you know how many
      genes you are about to export. ``effectDirection`` selects the up side,
      the down side, or both.

    A gene passes when the absolute effect size is at or above
    ``effectSizeThreshold`` and the p-value is at or below
    ``significanceThreshold``. Those are the same comparisons the plot uses, so
    the step's count matches the number you told the researcher.

    Leave ``attachToStepId`` unset to add the step as a new root. Set it, with
    ``slot``, to wire the step into an existing combine.

    Args:
        ctx: Agent run context.
        search_name: A specific EDA-backed search to use. Leave unset to use
            the generic subset or compute search.
        attach_to_step_id: The combine step to wire this into.
        slot: Which input of that combine to fill.
        effect_size_threshold: Minimum absolute effect size to keep.
        significance_threshold: Maximum p-value to keep.
        effect_direction: Which side of the volcano to keep.
    """
    binding = await bound_analysis(ctx)
    if binding is None:
        msg = (
            "No EDA analysis is open on this conversation. Call "
            "open_eda_analysis on the dataset you want, filter it with "
            "set_eda_filters, then export it."
        )
        raise ModelRetry(msg)
    _checked_thresholds(effect_size_threshold, significance_threshold)
    attach = _attach_point(attach_to_step_id, slot)

    analysis = await read_analysis(binding.site_id, analysis_id=binding.analysis_id)
    try:
        plan = eda_step_node(
            analysis,
            dataset_id=binding.dataset_id,
            thresholds=_thresholds(
                effect_size_threshold,
                significance_threshold,
                effect_direction,
            ),
            search_name=search_name,
        )
    except NoComputationError as exc:
        msg = (
            f"{exc} Call run_eda_compute to run the differential expression, "
            f"then export the genes that pass its thresholds."
        )
        raise ModelRetry(msg) from exc
    node = plan.node
    is_compute_backed = plan.is_compute_backed

    session = ctx.deps.runtime.strategy_session
    graph = get_graph(session, None)
    if graph is None:
        title = "No active strategy graph"
        detail = "create_eda_step needs an initialized graph in the session."
        raise ValidationError(title=title, detail=detail)

    result = await apply_operations_and_commit(
        deps=_strategy_context(ctx),
        ops=[AddLeafOp(step=node, attach=attach)],
    )
    sync = result.sync_result
    metadata: list[DataChunk] = [graph_snapshot_chunk(session, graph)]
    if sync is not None and sync.wdk_url is not None:
        metadata.append(
            strategy_link_chunk(
                strategy_id=graph.id,
                url=sync.wdk_url,
                title=graph.name,
            ),
        )
    wdk_strategy_id = sync.wdk_strategy_id if sync is not None else None
    created = EdaStepCreated(
        search_name=node.search_name,
        step_id=node.id,
        dataset_id=binding.dataset_id,
        analysis_id=binding.analysis_id,
        is_compute_backed=is_compute_backed,
        effect_size_threshold=effect_size_threshold,
        significance_threshold=significance_threshold,
        effect_direction=effect_direction if is_compute_backed else None,
        wdk_strategy_id=wdk_strategy_id,
        wdk_url=sync.wdk_url if sync is not None else None,
        failed_step_ids=result.failed_step_ids,
        guidance=_guidance(wdk_strategy_id, is_compute_backed=is_compute_backed),
    )
    if created.failed_step_ids:
        return with_summary(
            created,
            f"Step {node.id} added, {len(created.failed_step_ids)} steps failed",
            ctx=ctx,
            status="warn",
            extra=metadata,
        )
    return with_summary(
        created,
        f"Step {node.id} added to strategy {wdk_strategy_id}",
        ctx=ctx,
        extra=metadata,
    )
