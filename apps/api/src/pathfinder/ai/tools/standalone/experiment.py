"""Standalone experiment control test tools for pydantic-ai migration."""

from typing import Any

from pydantic_ai import RunContext

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.durable import durable_tool
from pathfinder.ai.tools.standalone._experiment_models import (
    DownloadLinks,
    SearchControlTestResult,
    StepControlTestResult,
)
from pathfinder.domain.strategy.types import DecodedParams
from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.platform.logging import get_logger
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONObject
from pathfinder.services.control_tests import (
    IntersectionConfig,
    run_positive_negative_controls,
)
from pathfinder.services.export import get_export_service

logger = get_logger(__name__)


async def _export_step_control_result(
    result: StepControlTestResult,
    name: str,
) -> StepControlTestResult:
    """Auto-attach download links to a step control test result."""
    try:
        svc = get_export_service()
        result_dict = result.model_dump(by_alias=True, exclude_none=True, mode="json")
        json_export = await svc.export_json(result_dict, name)
        result.downloads = DownloadLinks(
            json_url=json_export.url,
            expires_in_seconds=json_export.expires_in_seconds,
        )
    except (AppError, OSError) as e:
        logger.warning("Control test export failed", error=str(e))
    return result


async def _export_search_control_result(
    result: SearchControlTestResult,
    name: str,
) -> SearchControlTestResult:
    """Auto-attach download links to a search control test result."""
    try:
        svc = get_export_service()
        result_dict = result.model_dump(by_alias=True, exclude_none=True, mode="json")
        json_export = await svc.export_json(result_dict, name)
        result.downloads = DownloadLinks(
            json_url=json_export.url,
            expires_in_seconds=json_export.expires_in_seconds,
        )
    except (AppError, OSError) as e:
        logger.warning("Control test export failed", error=str(e))
    return result


@durable_tool(tool_name="run_control_tests_on_step", estimated_duration_seconds=180)
async def run_control_tests_on_step(
    ctx: RunContext[AgentDeps],
    wdk_step_id: int,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
) -> dict[str, Any]:
    """Run control tests against an already-built WDK strategy step.

    Durable: this tool defers work to the verification worker and the graph
    suspends via ``interrupt()`` while it runs. The resumed value is a dict
    matching :class:`StepControlTestResult`'s serialised shape.

    Tests directly against the strategy's actual results using Python set
    operations -- no temporary WDK strategy needed.  Use this after building
    a multi-step strategy with ``build_step`` / ``combine_steps``.

    For testing a standalone (not-yet-built) search, use
    ``run_control_tests_on_search`` instead.

    Args:
        ctx: Agent run context.
        wdk_step_id: WDK step ID from a built strategy to test against.
            Get the step ID from get_strategy(summary_only=false)
            (wdkStepId field on the root step).
        positive_controls: Known-positive IDs that should be returned.
        negative_controls: Known-negative IDs that should NOT be returned.
    """
    del ctx, wdk_step_id, positive_controls, negative_controls
    msg = "run_control_tests_on_step runs on the worker via @durable_tool"
    raise NotImplementedError(msg)


async def run_control_tests_on_search(
    ctx: RunContext[AgentDeps],
    target_search_name: str,
    target_parameters: DecodedParams,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
    record_type: str = "transcript",
) -> SearchControlTestResult | ToolErrorPayload:
    """Run control tests against a standalone WDK search (not a built strategy).

    Creates a temporary WDK strategy to intersect the search results with
    control gene IDs.  Use ``run_control_tests_on_step`` instead when you
    already have a built multi-step strategy.

    Controls are matched via ``GeneByLocusTag`` (parameter ``ds_gene_ids``).

    Args:
        ctx: Agent run context.
        target_search_name: WDK search/question urlSegment to test.
        target_parameters: Target search parameter mapping.
        positive_controls: Known-positive IDs that should be returned.
        negative_controls: Known-negative IDs that should NOT be returned.
        record_type: Record type. Defaults to 'transcript'.
    """
    has_positives = positive_controls and len(positive_controls) > 0
    has_negatives = negative_controls and len(negative_controls) > 0
    if not has_positives and not has_negatives:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "At least one of positive_controls or negative_controls must be provided.",
        )
    params_dict: JSONObject = dict(target_parameters)
    _cfg = IntersectionConfig(
        site_id=ctx.deps.site_id,
        record_type=record_type,
        target_search_name=target_search_name,
        target_parameters=params_dict,
        controls_search_name="GeneByLocusTag",
        controls_param_name="ds_gene_ids",
        controls_value_format="newline",
    )
    ctrl_result = await run_positive_negative_controls(
        _cfg,
        positive_controls=positive_controls,
        negative_controls=negative_controls,
    )
    ctrl_dict = ctrl_result.model_dump(by_alias=True, mode="json")
    result = SearchControlTestResult.model_validate(ctrl_dict)
    return await _export_search_control_result(
        result, f"{target_search_name}_control_tests"
    )
