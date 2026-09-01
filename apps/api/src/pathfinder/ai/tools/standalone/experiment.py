"""Standalone experiment control test tools for pydantic-ai migration."""

from typing import Any
from uuid import UUID

from assistant_core.graph.tool_summary import summary_chunks, with_summary
from assistant_core.platform.logging import get_logger
from assistant_core.platform.pydantic_base import CamelModel
from pydantic import ConfigDict, field_validator
from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn
from pydantic_ai.ui.vercel_ai.response_types import BaseChunk

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.durable import DurableOutcome, durable_tool
from pathfinder.ai.tools.standalone._experiment_models import (
    DownloadLinks,
    SearchControlTestResult,
    StepControlTestResult,
)
from pathfinder.domain.parameters.values import ParamValue
from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
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


class _RecoveredControls(CamelModel):
    """The positive-control recovery a control test reports."""

    model_config = ConfigDict(extra="ignore")

    positive_intersection: int = 0
    positive_controls_count: int = 0

    @field_validator("positive_intersection", "positive_controls_count", mode="before")
    @classmethod
    def _absent_is_zero(cls, value: object) -> object:
        return 0 if value is None else value


def controls_summary(counts: _RecoveredControls) -> str:
    """How many known positives the tested result set returned."""
    return (
        f"{counts.positive_intersection} of {counts.positive_controls_count} "
        f"positive controls recovered"
    )


def _control_test_chunks_from_result(
    resumed: Any,
    task_id: UUID,
    tool_call_id: str | None,
) -> list[BaseChunk]:
    del task_id
    outcome = DurableOutcome.model_validate(resumed)
    if not outcome.succeeded:
        return []
    counts = _RecoveredControls.model_validate(outcome.result)
    return summary_chunks(tool_call_id, controls_summary(counts))


@durable_tool(
    tool_name="run_control_tests_on_step",
    estimated_duration_seconds=180,
    chunks_from_result=_control_test_chunks_from_result,
)
async def run_control_tests_on_step(
    ctx: RunContext[AgentDeps],
    wdk_step_id: int,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
) -> dict[str, Any]:
    """Run control tests against an already-built WDK strategy step.

    Durable: this tool defers work to the verification worker and the turn
    ends while it runs. You are called again with a dict matching
    :class:`StepControlTestResult`'s serialised shape.

    Tests directly against the strategy's actual results using Python set
    operations -- no temporary WDK strategy needed.  Use this after a
    multi-step strategy is built with ``build_strategy``.

    For testing a standalone (not-yet-built) search, use
    ``run_control_tests_on_search`` instead.

    Args:
        ctx: Agent run context.
        wdk_step_id: WDK step ID from a built strategy to test against.
            Read it from get_strategy(summary_only=false): the root step
            carries the WDK step id.
        positive_controls: Known-positive IDs that should be returned.
        negative_controls: Known-negative IDs that should NOT be returned.
    """
    del ctx, wdk_step_id, positive_controls, negative_controls
    msg = "run_control_tests_on_step runs on the worker via @durable_tool"
    raise NotImplementedError(msg)


async def run_control_tests_on_search(
    ctx: RunContext[AgentDeps],
    target_search_name: str,
    target_parameters: dict[str, ParamValue],
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
    record_type: str = "transcript",
) -> ToolReturn[SearchControlTestResult | ToolErrorPayload]:
    """Run control tests against a standalone WDK search (not a built strategy).

    Creates a temporary WDK strategy to intersect the search results with
    control gene IDs.  Use ``run_control_tests_on_step`` instead when you
    already have a built multi-step strategy.

    Controls are matched via ``GeneByLocusTag`` (parameter ``ds_gene_ids``).

    Args:
        ctx: Agent run context.
        target_search_name: WDK search/question urlSegment to test.
        target_parameters: Target search parameter mapping. Each value MUST be
            wrapped in its typed shape - see the ``valueFormat`` field from
            ``get_search_overview`` for the per-param template.
        positive_controls: Known-positive IDs that should be returned.
        negative_controls: Known-negative IDs that should NOT be returned.
        record_type: Record type. Defaults to 'transcript'.
    """
    has_positives = positive_controls and len(positive_controls) > 0
    has_negatives = negative_controls and len(negative_controls) > 0
    if not has_positives and not has_negatives:
        return with_summary(
            tool_error(
                ErrorCode.VALIDATION_ERROR,
                "At least one of positive_controls or negative_controls "
                "must be provided.",
            ),
            "No control ids given to test against",
            ctx=ctx,
            status="warn",
        )
    _cfg = IntersectionConfig(
        site_id=ctx.deps.site_id,
        record_type=record_type,
        target_search_name=target_search_name,
        target_parameters=dict(target_parameters),
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
    exported = await _export_search_control_result(
        result, f"{target_search_name}_control_tests"
    )
    return with_summary(
        exported,
        controls_summary(_RecoveredControls.model_validate(exported.model_dump())),
        ctx=ctx,
    )
