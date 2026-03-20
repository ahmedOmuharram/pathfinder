"""Tools for attaching filters/analyses/reports to steps (AI-exposed)."""

from typing import Annotated

from kani import AIParam, ai_function

from veupath_chatbot.domain.strategy.ast import StepAnalysis, StepFilter, StepReport
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.strategies.engine.helpers import StrategyToolsHelpers


class StrategyAttachmentOps(StrategyToolsHelpers):
    """Tools that attach metadata/configuration to existing steps."""

    @ai_function()
    async def add_step_filter(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to filter")],
        filter_name: Annotated[str, AIParam(desc="Filter name")],
        value: Annotated[JSONValue, AIParam(desc="Filter value payload")],
        *,
        disabled: Annotated[
            bool, AIParam(desc="Whether the filter is disabled")
        ] = False,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Attach or update a filter on a step."""
        result = self._get_graph_and_step(graph_id, step_id)
        if isinstance(result, dict):
            return result
        graph, step = result

        existing = [f for f in step.filters if f.name != filter_name]
        existing.append(StepFilter(name=filter_name, value=value, disabled=disabled))
        step.filters = existing

        return self._step_ok_response(graph, step)

    @ai_function()
    async def add_step_analysis(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to analyze")],
        analysis_type: Annotated[str, AIParam(desc="Analysis type name")],
        parameters: Annotated[
            JSONObject | None, AIParam(desc="Analysis parameters")
        ] = None,
        custom_name: Annotated[
            str | None, AIParam(desc="Optional analysis name")
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Attach an analysis configuration to a step."""
        result = self._get_graph_and_step(graph_id, step_id)
        if isinstance(result, dict):
            return result
        graph, step = result

        step.analyses.append(
            StepAnalysis(
                analysis_type=analysis_type,
                parameters=parameters or {},
                custom_name=custom_name,
            )
        )

        return self._step_ok_response(graph, step)

    @ai_function()
    async def add_step_report(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to report")],
        report_name: Annotated[
            str, AIParam(desc="Report name (e.g., 'standard')")
        ] = "standard",
        config: Annotated[
            JSONObject | None, AIParam(desc="Report configuration")
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Attach a report configuration to a step."""
        result = self._get_graph_and_step(graph_id, step_id)
        if isinstance(result, dict):
            return result
        graph, step = result

        step.reports.append(StepReport(report_name=report_name, config=config or {}))

        return self._step_ok_response(graph, step)
