"""Standalone strategy attachment tools (filter, analysis, report) for pydantic-ai migration.

Each function takes ``RunContext[AgentDeps]`` and mirrors the original
:class:`StrategyAttachmentOps` methods exactly.
"""

from __future__ import annotations

from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._graph_helpers import step_ok_response
from pathfinder.ai.tools.standalone._stream_parts import (
    graph_snapshot_chunk,
    strategy_patch_chunk,
)
from pathfinder.ai.tools.standalone._validation_helpers import (
    StepOkResponse,
    get_graph_and_step,
)
from pathfinder.domain.strategy.ast import (
    PlanStepNode,
    StepAnalysis,
    StepFilter,
    StepReport,
)
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.platform.tool_errors import ToolErrorPayload
from pathfinder.platform.types import JSONObject, JSONValue


def _step_updated_return(
    session: StrategySession, graph: StrategyGraph, step: PlanStepNode
) -> ToolReturn[StepOkResponse]:
    """Wrap an attachment-mutation success into a ToolReturn with chunks."""
    return ToolReturn(
        return_value=step_ok_response(session, graph, step),
        metadata=[
            graph_snapshot_chunk(session, graph),
            strategy_patch_chunk(
                graph, step,
                operation="update_step",
                sync_state=session.sync_state,
            ),
        ],
    )


async def add_step_filter(
    ctx: RunContext[AgentDeps],
    step_id: str,
    filter_name: str,
    value: JSONValue,
    *,
    disabled: bool = False,
    graph_id: str | None = None,
) -> ToolReturn[StepOkResponse] | ToolErrorPayload:
    """Attach or update a WDK filter on a step.

    Filters narrow a step's result set without changing its search.
    If a filter with the same name already exists it is replaced.

    Args:
        step_id: ID of the step to filter.
        filter_name: WDK filter name (e.g. 'gene_boolean_filter_array').
        value: Filter value (shape depends on the filter type).
        disabled: If True the filter is stored but not applied.
        graph_id: Target graph. Uses the active graph if omitted.
    """
    deps = ctx.deps
    session = deps.strategy_session

    result = get_graph_and_step(session, graph_id, step_id)
    if isinstance(result, ToolErrorPayload):
        return result
    graph, step = result

    existing = [f for f in step.filters if f.name != filter_name]
    existing.append(StepFilter(name=filter_name, value=value, disabled=disabled))
    step.filters = existing

    return _step_updated_return(session, graph, step)


async def add_step_analysis(
    ctx: RunContext[AgentDeps],
    step_id: str,
    analysis_type: str,
    parameters: JSONObject | None = None,
    custom_name: str | None = None,
    graph_id: str | None = None,
) -> ToolReturn[StepOkResponse] | ToolErrorPayload:
    """Attach an analysis configuration to a step.

    Analyses run server-side computations on a step's result set
    (e.g. GO enrichment, word enrichment, pathway enrichment).
    Multiple analyses can be attached to the same step.

    Args:
        step_id: ID of the step to analyze.
        analysis_type: Analysis plugin name (e.g. 'word-enrichment').
        parameters: Analysis-specific configuration.
        custom_name: Human-readable label for this analysis.
        graph_id: Target graph. Uses the active graph if omitted.
    """
    deps = ctx.deps
    session = deps.strategy_session

    result = get_graph_and_step(session, graph_id, step_id)
    if isinstance(result, ToolErrorPayload):
        return result
    graph, step = result

    step.analyses.append(
        StepAnalysis(
            analysis_type=analysis_type,
            parameters=parameters or {},
            custom_name=custom_name,
        )
    )

    return _step_updated_return(session, graph, step)


async def add_step_report(
    ctx: RunContext[AgentDeps],
    step_id: str,
    report_name: str = "standard",
    config: JSONObject | None = None,
    graph_id: str | None = None,
) -> ToolReturn[StepOkResponse] | ToolErrorPayload:
    """Attach a report configuration to a step.

    Reports control how step results are formatted for download or
    display (e.g. tabular, XML, JSON). The default report is 'standard'.

    Args:
        step_id: ID of the step.
        report_name: WDK reporter name (default: 'standard').
        config: Reporter-specific configuration.
        graph_id: Target graph. Uses the active graph if omitted.
    """
    deps = ctx.deps
    session = deps.strategy_session

    result = get_graph_and_step(session, graph_id, step_id)
    if isinstance(result, ToolErrorPayload):
        return result
    graph, step = result

    step.reports.append(StepReport(report_name=report_name, config=config or {}))

    return _step_updated_return(session, graph, step)
