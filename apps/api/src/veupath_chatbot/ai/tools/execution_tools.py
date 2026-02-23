"""Tools for executing strategies and retrieving results."""

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.domain.strategy.compile import compile_strategy
from veupath_chatbot.domain.strategy.session import StrategyGraph, StrategySession
from veupath_chatbot.domain.strategy.validate import validate_strategy
from veupath_chatbot.integrations.veupathdb.factory import (
    get_results_api,
    get_site,
    get_strategy_api,
)
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI
from veupath_chatbot.platform.errors import ErrorCode, WDKError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject, JSONValue

logger = get_logger(__name__)


class ExecutionTools:
    """Tools for running strategies and getting results."""

    def __init__(self, session: StrategySession) -> None:
        self.session = session

    def _get_graph(self, graph_id: str | None) -> StrategyGraph | None:
        return self.session.get_graph(graph_id)

    def _graph_not_found(self, graph_id: str | None) -> JSONObject:
        if graph_id:
            return self._tool_error(
                ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id
            )
        return self._tool_error(
            ErrorCode.NOT_FOUND, "Graph not found. Provide a graphId.", graphId=graph_id
        )

    def _tool_error(
        self, code: ErrorCode | str, message: str, **details: object
    ) -> JSONObject:
        # Convert details to JSONValue-compatible types
        json_details: dict[str, JSONValue] = {}
        for key, value in details.items():
            # Convert object to JSONValue - only include JSON-serializable types
            if isinstance(value, (str, int, float, bool, type(None))):
                json_details[key] = value
            elif isinstance(value, list):
                # Convert list elements to JSONValue recursively
                json_list: list[JSONValue] = []
                for item in value:
                    if isinstance(item, (str, int, float, bool, type(None))):
                        json_list.append(item)
                    elif isinstance(item, (list, dict)):
                        json_list.append(cast(JSONValue, item))
                    else:
                        json_list.append(str(item))
                json_details[key] = json_list
            elif isinstance(value, dict):
                # Convert dict to JSONObject
                json_dict: dict[str, JSONValue] = {}
                for k, v in value.items():
                    if isinstance(v, (str, int, float, bool, type(None))):
                        json_dict[str(k)] = v
                    elif isinstance(v, (list, dict)):
                        json_dict[str(k)] = cast(JSONValue, v)
                    else:
                        json_dict[str(k)] = str(v)
                json_details[key] = json_dict
            else:
                # Convert other types to string
                json_details[key] = str(value)
        return tool_error(code, message, **json_details)

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
    ) -> JSONObject:
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
    ) -> JSONObject:
        """Build or update the current strategy on VEuPathDB.

        If the strategy has already been built (a WDK strategy ID exists),
        this updates it in place.  Otherwise it creates a new WDK strategy.
        Returns per-step result counts, zero-result step detection, and the
        WDK strategy URL.
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        strategy = graph.current_strategy

        if root_step_id:
            # Explicit override — trust the caller.
            root_step = graph.get_step(root_step_id)
        elif len(graph.roots) == 1:
            root_step = graph.get_step(next(iter(graph.roots)))
        elif len(graph.roots) > 1:
            return self._tool_error(
                ErrorCode.INVALID_STRATEGY,
                f"Graph has {len(graph.roots)} subtree roots — expected exactly 1 to build. "
                "Combine them first, or specify root_step_id.",
                graphId=graph.id,
                roots=cast(JSONValue, sorted(graph.roots)),
            )
        else:
            root_step = None

        needs_rebuild = root_step is not None and (
            not strategy
            or (
                root_step.id is not None
                and strategy.get_step_by_id(root_step.id) is None
            )
        )

        if not strategy or needs_rebuild:
            if not root_step:
                return self._tool_error(
                    ErrorCode.INVALID_STRATEGY,
                    "No steps in graph. Create steps before building.",
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
            validation_result = validate_strategy(strategy)
            if not validation_result.valid:
                return self._tool_error(
                    ErrorCode.VALIDATION_ERROR,
                    "Strategy validation failed",
                    graphId=graph.id,
                    validationErrors=[
                        {"path": e.path, "message": e.message}
                        for e in validation_result.errors
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
            compilation_result = await compile_strategy(
                strategy, api, site_id=self.session.site_id
            )

            # Create-or-update: if a WDK strategy already exists on the graph,
            # update it rather than creating a duplicate.
            existing_wdk_id = graph.wdk_strategy_id
            wdk_strategy_id: int | None = None

            if existing_wdk_id is not None:
                # Update the existing WDK strategy.
                try:
                    await api.update_strategy(
                        strategy_id=existing_wdk_id,
                        step_tree=compilation_result.step_tree,
                        name=strategy.name or "Untitled Strategy",
                    )
                    wdk_strategy_id = existing_wdk_id
                    logger.info(
                        "Updated existing WDK strategy",
                        wdk_strategy_id=existing_wdk_id,
                    )
                except Exception as update_err:
                    # If the old strategy was deleted (404), fall through to create.
                    logger.warning(
                        "Failed to update WDK strategy, will create new",
                        wdk_strategy_id=existing_wdk_id,
                        error=str(update_err),
                    )
                    wdk_strategy_id = None

            if wdk_strategy_id is None:
                # First build (or update failed) — create a new WDK strategy.
                wdk_result = await api.create_strategy(
                    step_tree=compilation_result.step_tree,
                    name=strategy.name or "Untitled Strategy",
                    description=strategy.description,
                )
                if isinstance(wdk_result, dict):
                    raw_id = wdk_result.get("id")
                    if isinstance(raw_id, int):
                        wdk_strategy_id = raw_id

            compiled_map = {s.local_id: s.wdk_step_id for s in compilation_result.steps}

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
                site.strategy_url(wdk_strategy_id, compilation_result.root_step_id)
                if wdk_strategy_id
                else None
            )

            # Store the local→WDK step ID mapping on the graph so that
            # list_current_steps can surface wdkStepId per step.
            graph.wdk_step_ids = dict(compiled_map)
            graph.wdk_strategy_id = wdk_strategy_id

            # Fetch the strategy once — WDK includes estimatedSize on every
            # step, so one GET replaces N individual report POST calls.
            step_counts: dict[str, int | None] = {}
            root_count: int | None = None
            if wdk_strategy_id is not None:
                try:
                    strategy_info = await api.get_strategy(wdk_strategy_id)
                    if isinstance(strategy_info, dict):
                        root_step_id_raw = strategy_info.get("rootStepId")
                        steps_raw = strategy_info.get("steps")
                        if isinstance(steps_raw, dict):
                            # Build a reverse map: wdk_step_id → local_id
                            wdk_to_local = {v: k for k, v in compiled_map.items()}
                            for wdk_id_str, step_info in steps_raw.items():
                                if not isinstance(step_info, dict):
                                    continue
                                estimated = step_info.get("estimatedSize")
                                count_val = (
                                    estimated if isinstance(estimated, int) else None
                                )
                                # Map back to local step ID
                                try:
                                    wdk_id_int = int(wdk_id_str)
                                except ValueError, TypeError:
                                    continue
                                local_id = wdk_to_local.get(wdk_id_int)
                                if local_id:
                                    step_counts[local_id] = count_val
                            # Extract root count specifically
                            if isinstance(root_step_id_raw, int):
                                root_local = wdk_to_local.get(root_step_id_raw)
                                if root_local:
                                    root_count = step_counts.get(root_local)
                except Exception as e:
                    logger.warning("Strategy count lookup failed", error=str(e))

            # Persist counts on the graph for list_current_steps.
            graph.step_counts = step_counts

            # Build per-step counts response keyed by local step ID.
            counts_response: JSONObject = {str(k): v for k, v in step_counts.items()}
            zeros = sorted([sid for sid, c in step_counts.items() if c == 0])

            wdk_strategy_id_value: JSONValue = wdk_strategy_id
            return {
                "ok": True,
                "graphId": graph.id,
                "graphName": graph.name,
                "name": strategy.name,
                "description": strategy.description,
                "wdkStrategyId": wdk_strategy_id_value,
                "wdkUrl": wdk_url,
                "rootStepId": compilation_result.root_step_id,
                "resultCount": root_count,
                "stepCount": len(compilation_result.steps),
                "counts": counts_response,
                "zeroStepIds": cast(JSONValue, zeros),
                "zeroCount": len(zeros),
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
    ) -> JSONObject:
        """Get the result count for a built step.

        Use after build_strategy to check result sizes.
        For imported WDK strategies, provide wdk_strategy_id.
        """
        try:
            api = self._get_api()
            if wdk_strategy_id is not None:
                strategy_raw = await api.get_strategy(wdk_strategy_id)
                if not isinstance(strategy_raw, dict):
                    raise TypeError("Expected dict from get_strategy")
                # WDK: steps is dict[str, stepObj], estimatedSize is on each step.
                steps_raw = strategy_raw.get("steps")
                if isinstance(steps_raw, dict):
                    step_info = steps_raw.get(str(wdk_step_id))
                    if isinstance(step_info, dict):
                        estimated_size = step_info.get("estimatedSize")
                        if isinstance(estimated_size, int):
                            return {"stepId": wdk_step_id, "count": estimated_size}
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
    ) -> JSONObject:
        """Get a download URL for step results.

        The URL can be used to download results in the specified format.
        """
        if not isinstance(wdk_step_id, int) or wdk_step_id <= 0:
            return self._tool_error(
                ErrorCode.VALIDATION_ERROR,
                "wdk_step_id must be a positive integer.",
                wdk_step_id=wdk_step_id,
                expected="positive integer",
            )
        if format not in {"csv", "tab", "json"}:
            return self._tool_error(
                ErrorCode.VALIDATION_ERROR,
                "format must be one of: csv, tab, json.",
                format=format,
                allowed=["csv", "tab", "json"],
            )
        if attributes is not None:
            if len(attributes) == 0:
                return self._tool_error(
                    ErrorCode.VALIDATION_ERROR,
                    "attributes cannot be an empty list when provided.",
                    attributes=attributes,
                )
            bad_attrs = [
                a for a in attributes if not isinstance(a, str) or not a.strip()
            ]
            if bad_attrs:
                return self._tool_error(
                    ErrorCode.VALIDATION_ERROR,
                    "attributes must contain non-empty strings.",
                    invalidAttributes=cast(JSONValue, bad_attrs),
                )

        try:
            results_api = self._get_results_api()
            url = await results_api.get_download_url(
                step_id=wdk_step_id,
                format=format,
                attributes=attributes,
            )
            if not isinstance(url, str) or not url:
                return self._tool_error(
                    ErrorCode.WDK_ERROR,
                    "VEuPathDB did not provide a usable download URL for this step. "
                    "This usually means the temporary result is still being prepared "
                    "or the upstream payload shape changed.",
                    wdk_step_id=wdk_step_id,
                    format=format,
                )
            return {
                "downloadUrl": url,
                "format": format,
                "stepId": wdk_step_id,
            }
        except WDKError as e:
            if e.status == 404:
                return self._tool_error(
                    ErrorCode.WDK_ERROR,
                    "Step not found in VEuPathDB. The step ID may be stale, from a different session, or not built yet. Build/rebuild the strategy and use a fresh step ID from this run.",
                    wdk_step_id=wdk_step_id,
                    http_status=e.status,
                )
            if e.status == 400 and "reportName" in (e.detail or ""):
                return self._tool_error(
                    ErrorCode.WDK_ERROR,
                    "VEuPathDB rejected the download request payload (missing/invalid reportName). This is a server integration issue, not your step data.",
                    wdk_step_id=wdk_step_id,
                    http_status=e.status,
                )
            if e.status in (401, 403):
                return self._tool_error(
                    ErrorCode.WDK_ERROR,
                    "Not authorized to download this step in VEuPathDB. Re-authenticate and retry, or use a step ID from your own strategy.",
                    wdk_step_id=wdk_step_id,
                    http_status=e.status,
                )
            if e.status >= 500:
                return self._tool_error(
                    ErrorCode.WDK_ERROR,
                    "VEuPathDB is temporarily unavailable while generating the download URL. Please retry in a moment.",
                    wdk_step_id=wdk_step_id,
                    http_status=e.status,
                )
            return self._tool_error(
                ErrorCode.WDK_ERROR,
                f"VEuPathDB rejected get_download_url for step {wdk_step_id}: {e.detail}",
                wdk_step_id=wdk_step_id,
                http_status=e.status,
            )
        except Exception as e:
            return self._tool_error(
                ErrorCode.WDK_ERROR,
                "Failed to generate download URL from VEuPathDB.",
                wdk_step_id=wdk_step_id,
                detail=str(e),
            )

    @ai_function()
    async def get_sample_records(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step ID")],
        limit: Annotated[int, AIParam(desc="Number of records")] = 5,
    ) -> JSONObject:
        """Get a sample of records from an executed step.

        Returns the first N records to show the user what data is available.
        """
        if not isinstance(wdk_step_id, int) or wdk_step_id <= 0:
            return self._tool_error(
                ErrorCode.VALIDATION_ERROR,
                "wdk_step_id must be a positive integer.",
                wdk_step_id=wdk_step_id,
                expected="positive integer",
            )
        if not isinstance(limit, int) or limit < 1 or limit > 500:
            return self._tool_error(
                ErrorCode.VALIDATION_ERROR,
                "limit must be an integer between 1 and 500.",
                limit=limit,
                min=1,
                max=500,
            )

        try:
            # Use the standard report endpoint via StrategyAPI rather than the
            # legacy /answer endpoint. This avoids opaque 404s on deployments
            # that do not expose /answer for current-user steps.
            strategy_api = self._get_api()
            preview_raw = await strategy_api.get_step_answer(
                step_id=wdk_step_id,
                pagination={"offset": 0, "numRecords": limit},
            )
            if not isinstance(preview_raw, dict):
                raise TypeError("Expected dict from get_step_preview")
            preview: dict[str, JSONValue] = {str(k): v for k, v in preview_raw.items()}
            records_raw = preview.get("records", [])
            records: list[JSONValue] = (
                records_raw if isinstance(records_raw, list) else []
            )
            meta_raw = preview.get("meta", {})
            meta: dict[str, JSONValue] = meta_raw if isinstance(meta_raw, dict) else {}
            total_count_raw = meta.get("totalCount", 0)
            total_count: int = (
                total_count_raw if isinstance(total_count_raw, int) else 0
            )
            attributes_list: list[str] = []
            if records and isinstance(records[0], dict):
                attributes_list = [str(k) for k in records[0]]
            # Convert to JSONValue-compatible type (list[str] is compatible with list[JSONValue])
            attributes: JSONValue = cast(JSONValue, attributes_list)
            return {
                "records": records,
                "totalCount": total_count,
                "attributes": attributes,
            }
        except WDKError as e:
            if e.status == 404:
                return self._tool_error(
                    ErrorCode.WDK_ERROR,
                    "Step not found in VEuPathDB. The step ID may be stale, from a different session, or not built yet. Build/rebuild the strategy and use a fresh step ID from this run.",
                    wdk_step_id=wdk_step_id,
                    http_status=e.status,
                )
            if e.status in (401, 403):
                return self._tool_error(
                    ErrorCode.WDK_ERROR,
                    "Not authorized to read this step in VEuPathDB. Re-authenticate and retry, or use a step ID from your own strategy.",
                    wdk_step_id=wdk_step_id,
                    http_status=e.status,
                )
            if e.status >= 500:
                return self._tool_error(
                    ErrorCode.WDK_ERROR,
                    "VEuPathDB is temporarily unavailable while reading step records. Please retry in a moment.",
                    wdk_step_id=wdk_step_id,
                    http_status=e.status,
                )
            return self._tool_error(
                ErrorCode.WDK_ERROR,
                f"VEuPathDB rejected get_sample_records for step {wdk_step_id}: {e.detail}",
                wdk_step_id=wdk_step_id,
                http_status=e.status,
            )
        except Exception as e:
            return self._tool_error(
                ErrorCode.WDK_ERROR,
                "Failed to fetch sample records from VEuPathDB.",
                wdk_step_id=wdk_step_id,
                detail=str(e),
            )
