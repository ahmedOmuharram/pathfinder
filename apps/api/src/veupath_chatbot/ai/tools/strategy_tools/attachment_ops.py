"""Tools for attaching filters/analyses/reports to steps (AI-exposed)."""

from __future__ import annotations

from typing import Annotated, Any

from kani import AIParam, ai_function

from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.domain.strategy.ast import StepAnalysis, StepFilter, StepReport


class StrategyAttachmentOps:
    """Tools that attach metadata/configuration to existing steps."""

    @ai_function()
    async def add_step_filter(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to filter")],
        filter_name: Annotated[str, AIParam(desc="Filter name")],
        value: Annotated[Any, AIParam(desc="Filter value payload")],
        disabled: Annotated[bool, AIParam(desc="Whether the filter is disabled")] = False,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> dict[str, Any]:
        """Attach or update a filter on a step."""
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        step = graph.get_step(step_id)
        if not step:
            return self._tool_error(
                ErrorCode.STEP_NOT_FOUND, f"Step not found: {step_id}", stepId=step_id
            )

        existing = [f for f in step.filters if f.name != filter_name]
        existing.append(StepFilter(name=filter_name, value=value, disabled=disabled))
        step.filters = existing

        response = self._serialize_step(graph, step)
        response["ok"] = True
        return self._with_full_graph(graph, response)

    @ai_function()
    async def add_step_analysis(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to analyze")],
        analysis_type: Annotated[str, AIParam(desc="Analysis type name")],
        parameters: Annotated[dict[str, Any] | None, AIParam(desc="Analysis parameters")] = None,
        custom_name: Annotated[str | None, AIParam(desc="Optional analysis name")] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> dict[str, Any]:
        """Attach an analysis configuration to a step."""
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        step = graph.get_step(step_id)
        if not step:
            return self._tool_error(
                ErrorCode.STEP_NOT_FOUND, f"Step not found: {step_id}", stepId=step_id
            )

        step.analyses.append(
            StepAnalysis(
                analysis_type=analysis_type,
                parameters=parameters or {},
                custom_name=custom_name,
            )
        )

        response = self._serialize_step(graph, step)
        response["ok"] = True
        return self._with_full_graph(graph, response)

    @ai_function()
    async def add_step_report(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to report")],
        report_name: Annotated[str, AIParam(desc="Report name (e.g., 'standard')")] = "standard",
        config: Annotated[dict[str, Any] | None, AIParam(desc="Report configuration")] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> dict[str, Any]:
        """Attach a report configuration to a step."""
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        step = graph.get_step(step_id)
        if not step:
            return self._tool_error(
                ErrorCode.STEP_NOT_FOUND, f"Step not found: {step_id}", stepId=step_id
            )

        step.reports.append(StepReport(report_name=report_name, config=config or {}))

        response = self._serialize_step(graph, step)
        response["ok"] = True
        return self._with_full_graph(graph, response)

