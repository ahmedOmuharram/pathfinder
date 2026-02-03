"""Tools for executing strategies and retrieving results."""

from typing import Annotated, Any

from kani import AIParam, ai_function

from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.domain.strategy.compile import compile_strategy
from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.domain.strategy.validate import validate_strategy
from veupath_chatbot.integrations.veupathdb.factory import (
    get_results_api,
    get_site,
    get_strategy_api,
)
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI
from veupath_chatbot.services.strategy_session import StrategyGraph, StrategySession

logger = get_logger(__name__)


class ExecutionTools:
    """Tools for running strategies and getting results."""

    def __init__(self, session: StrategySession) -> None:
        self.session = session

    def _get_graph(self, graph_id: str | None) -> StrategyGraph | None:
        return self.session.get_graph(graph_id)

    def _graph_not_found(self, graph_id: str | None) -> dict[str, Any]:
        if graph_id:
            return self._tool_error(
                ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id
            )
        return self._tool_error(
            ErrorCode.NOT_FOUND, "Graph not found. Provide a graphId.", graphId=graph_id
        )

    def _tool_error(self, code: ErrorCode | str, message: str, **details: Any) -> dict[str, Any]:
        return tool_error(code, message, **details)

    def _get_api(self) -> StrategyAPI:
        """Get strategy API for current site."""
        return get_strategy_api(self.session.site_id)

    def _get_results_api(self) -> TemporaryResultsAPI:
        """Get temporary results API."""
        return get_results_api(self.session.site_id)

    @ai_function()
    async def preview_results(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to preview")],
        limit: Annotated[int, AIParam(desc="Max records to return")] = 10,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to use")] = None,
    ) -> dict[str, Any]:
        """Preview results from a step.

        Returns a sample of records and the total count.
        Use this to check if a step returns expected results before
        building a full strategy.
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        step = graph.get_step(step_id)

        if not step:
            return self._tool_error(
                ErrorCode.STEP_NOT_FOUND, f"Step not found: {step_id}", graphId=graph.id
            )

        # For now, return a simulated preview
        # In production, this would compile and execute the step
        return {
            "graphId": graph.id,
            "stepId": step_id,
            "status": "preview_simulated",
            "message": (
                "Preview functionality requires executing the step on VEuPathDB. "
                "Build the full strategy to get actual results."
            ),
        }

    @ai_function()
    async def build_strategy(
        self,
        strategy_name: Annotated[str | None, AIParam(desc="Strategy name")] = None,
        root_step_id: Annotated[
            str | None, AIParam(desc="Root step ID (required if not built)")
        ] = None,
        record_type: Annotated[
            str | None, AIParam(desc="Record type (required if not built)")
        ] = None,
        description: Annotated[str | None, AIParam(desc="Strategy description")] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to build")] = None,
    ) -> dict[str, Any]:
        """Build the current strategy on VEuPathDB.

        This compiles all steps and creates the strategy on the WDK server,
        returning the WDK strategy ID and result count.
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        latest_step_id = graph.last_step_id
        latest_step = graph.get_step(latest_step_id) if latest_step_id else None
        strategy = graph.current_strategy
        needs_rebuild = latest_step is not None and (
            not strategy or strategy.get_step_by_id(latest_step_id) is None
        )

        if not strategy or needs_rebuild:
            root_step = graph.get_step(root_step_id) if root_step_id else latest_step
            if not root_step:
                return self._tool_error(
                    ErrorCode.INVALID_STRATEGY,
                    "No strategy built. Provide root_step_id and record_type.",
                    graphId=graph.id,
                )

            inferred_record_type = record_type or graph.record_type
            if not inferred_record_type:
                return self._tool_error(
                    ErrorCode.VALIDATION_ERROR,
                    "Record type could not be inferred for execution.",
                    graphId=graph.id,
                )

            strategy = StrategyAST(
                record_type=inferred_record_type,
                root=root_step,
                name=strategy_name or graph.name,
                description=description,
            )
            result = validate_strategy(strategy)
            if not result.valid:
                return self._tool_error(
                    ErrorCode.VALIDATION_ERROR,
                    "Strategy validation failed",
                    graphId=graph.id,
                    validationErrors=[
                        {"path": e.path, "message": e.message}
                        for e in result.errors
                    ],
                )

            graph.current_strategy = strategy
            graph.save_history(
                f"Created strategy: {strategy_name or 'Untitled Strategy'}"
            )
        if strategy_name:
            strategy.name = strategy_name
            graph.name = strategy_name

        try:
            api = self._get_api()

            # Compile to WDK
            logger.info("Building strategy", name=strategy.name)
            result = await compile_strategy(strategy, api, site_id=self.session.site_id)

            # Create the strategy
            wdk_result = await api.create_strategy(
                step_tree=result.step_tree,
                name=strategy.name or "Untitled Strategy",
                description=strategy.description,
            )

            wdk_strategy_id = wdk_result.get("strategyId") or wdk_result.get("id")
            compiled_map = {s.local_id: s.wdk_step_id for s in result.steps}

            for step in strategy.get_all_steps():
                wdk_step_id = compiled_map.get(step.id)
                if not wdk_step_id:
                    continue
                for step_filter in getattr(step, "filters", []) or []:
                    await api.set_step_filter(
                        step_id=wdk_step_id,
                        filter_name=step_filter.name,
                        value=step_filter.value,
                        disabled=step_filter.disabled,
                    )
                for analysis in getattr(step, "analyses", []) or []:
                    await api.run_step_analysis(
                        step_id=wdk_step_id,
                        analysis_type=analysis.analysis_type,
                        parameters=analysis.parameters,
                        custom_name=analysis.custom_name,
                    )
                for report in getattr(step, "reports", []) or []:
                    await api.run_step_report(
                        step_id=wdk_step_id,
                        report_name=report.report_name,
                        config=report.config,
                    )
            site = get_site(self.session.site_id)
            wdk_url = (
                site.strategy_url(wdk_strategy_id, result.root_step_id)
                if wdk_strategy_id
                else None
            )

            # Get result count (best-effort; some WDK deployments don't expose /answer)
            count = None
            try:
                count = await api.get_step_count(result.root_step_id)
            except Exception as e:
                logger.warning("Result count unavailable", error=str(e))

            if count is None and wdk_strategy_id:
                try:
                    strategy_info = await api.get_strategy(wdk_strategy_id)
                    root_step_id = strategy_info.get("rootStepId")
                    steps = strategy_info.get("steps", {})
                    root_info = steps.get(str(root_step_id))
                    if isinstance(root_info, dict):
                        count = root_info.get("estimatedSize")
                except Exception as e:
                    logger.warning("Strategy count lookup failed", error=str(e))

            return {
                "ok": True,
                "graphId": graph.id,
                "graphName": graph.name,
                "name": strategy.name,
                "description": strategy.description,
                "wdkStrategyId": wdk_strategy_id,
                "wdkUrl": wdk_url,
                "rootStepId": result.root_step_id,
                "resultCount": count,
                "stepCount": len(result.steps),
            }

        except Exception as e:
            logger.error("Strategy build failed", error=str(e))
            return self._tool_error(
                ErrorCode.WDK_ERROR, f"Build failed: {e}", graphId=graph.id
            )

    @ai_function()
    async def get_result_count(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step ID")],
        wdk_strategy_id: Annotated[
            int | None, AIParam(desc="WDK strategy ID (for imports)")
        ] = None,
    ) -> dict[str, Any]:
        """Get the result count for a built step.

        Use after build_strategy to check result sizes.
        For imported WDK strategies, provide wdk_strategy_id.
        """
        try:
            api = self._get_api()
            if wdk_strategy_id is not None:
                strategy = await api.get_strategy(wdk_strategy_id)
                steps = strategy.get("steps") or {}
                step_info = steps.get(str(wdk_step_id)) or steps.get(wdk_step_id)
                if isinstance(step_info, dict):
                    count = step_info.get("estimatedSize") or step_info.get("estimated_size")
                    if isinstance(count, int):
                        return {"stepId": wdk_step_id, "count": count}
            count = await api.get_step_count(wdk_step_id)
            return {"stepId": wdk_step_id, "count": count}
        except Exception as e:
            message = str(e)
            if wdk_strategy_id is None:
                message = f"{message} (try providing wdk_strategy_id)"
            return self._tool_error(ErrorCode.WDK_ERROR, message)

    @ai_function()
    async def get_download_url(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step ID")],
        format: Annotated[
            str,
            AIParam(desc="Download format: csv, tab, or json"),
        ] = "csv",
        attributes: Annotated[
            list[str] | None,
            AIParam(desc="Specific attributes to include"),
        ] = None,
    ) -> dict[str, Any]:
        """Get a download URL for step results.

        The URL can be used to download results in the specified format.
        """
        try:
            results_api = self._get_results_api()
            url = await results_api.get_download_url(
                step_id=wdk_step_id,
                format=format,
                attributes=attributes,
            )
            return {
                "downloadUrl": url,
                "format": format,
                "stepId": wdk_step_id,
            }
        except Exception as e:
            return self._tool_error(ErrorCode.WDK_ERROR, str(e))

    @ai_function()
    async def get_sample_records(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step ID")],
        limit: Annotated[int, AIParam(desc="Number of records")] = 5,
    ) -> dict[str, Any]:
        """Get a sample of records from an executed step.

        Returns the first N records to show the user what data is available.
        """
        try:
            results_api = self._get_results_api()
            preview = await results_api.get_step_preview(
                step_id=wdk_step_id,
                limit=limit,
            )
            return {
                "records": preview.get("records", []),
                "totalCount": preview.get("meta", {}).get("totalCount", 0),
                "attributes": list(preview.get("records", [{}])[0].keys())
                if preview.get("records")
                else [],
            }
        except Exception as e:
            return self._tool_error(ErrorCode.WDK_ERROR, str(e))

