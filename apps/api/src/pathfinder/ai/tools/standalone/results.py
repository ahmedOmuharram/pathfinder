"""Standalone result tools for pydantic-ai agents.

Provides:
- ``get_sample_records`` -- get a sample of records from an executed step
- ``get_download_url`` -- get a download URL for step results
"""

from assistant_core.graph.tool_summary import with_summary
from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._result_models import (
    DownloadUrlResult,
    SampleRecordsResult,
    _extract_sample_response,
    _fetch_download_url,
    _fetch_step_preview,
    _sample_attributes,
    _validate_download_url_inputs,
    _validate_sample_inputs,
)
from pathfinder.platform.errors import ErrorCode
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.services.wdk import get_results_api, get_strategy_api


async def get_download_url(
    ctx: RunContext[AgentDeps],
    wdk_step_id: int,
    output_format: str = "csv",
    attributes: list[str] | None = None,
) -> ToolReturn[DownloadUrlResult | ToolErrorPayload]:
    """Get a download URL for step results.

    The step must already be built in WDK. The returned URL is
    temporary and will expire after the WDK session ends.

    Args:
        wdk_step_id: WDK step ID. The step must be built in WDK first.
        output_format: Download format: csv, tab, or json.
        attributes: Specific attributes to include in the download.
    """
    _validate_download_url_inputs(wdk_step_id, output_format)

    site_id = ctx.deps.strategy_session.site_id
    url_or_error = await _fetch_download_url(
        get_results_api(site_id),
        wdk_step_id,
        output_format,
        attributes,
    )
    if isinstance(url_or_error, ToolErrorPayload):
        return _no_download(ctx, url_or_error, output_format)
    if not url_or_error:
        return _no_download(
            ctx,
            tool_error(
                ErrorCode.WDK_ERROR,
                "VEuPathDB did not provide a usable download URL for this step. "
                "This usually means the temporary result is still being prepared "
                "or the upstream payload shape changed.",
                wdk_step_id=wdk_step_id,
                output_format=output_format,
            ),
            output_format,
        )
    return with_summary(
        DownloadUrlResult(
            download_url=url_or_error,
            format=output_format,
            step_id=wdk_step_id,
        ),
        f"{output_format.upper()} download ready",
        ctx=ctx,
    )


def _no_download(
    ctx: RunContext[AgentDeps],
    payload: ToolErrorPayload,
    output_format: str,
) -> ToolReturn[DownloadUrlResult | ToolErrorPayload]:
    """VEuPathDB refused the download this call asked for."""
    return with_summary(
        payload,
        f"No {output_format.upper()} download for this step",
        ctx=ctx,
        status="warn",
    )


async def get_sample_records(
    ctx: RunContext[AgentDeps],
    wdk_step_id: int,
    limit: int = 5,
) -> ToolReturn[SampleRecordsResult | ToolErrorPayload]:
    """Get a sample of records from an executed step.

    The step must already be built in WDK. Returns the first N records - each
    with its id plus, for gene/transcript steps, the product description, gene
    symbol, and organism - to show the user what data is available.

    Args:
        wdk_step_id: WDK step ID. The step must be built in WDK first.
        limit: Number of records to return.
    """
    _validate_sample_inputs(wdk_step_id, limit)

    session = ctx.deps.strategy_session
    graph = session.get_graph(None)
    record_type = graph.record_type if graph is not None else None
    preview_or_error = await _fetch_step_preview(
        get_strategy_api(session.site_id),
        wdk_step_id,
        limit,
        _sample_attributes(record_type),
    )
    if isinstance(preview_or_error, ToolErrorPayload):
        return with_summary(
            preview_or_error,
            f"No sample records from step {wdk_step_id}",
            ctx=ctx,
            status="warn",
        )
    sample = _extract_sample_response(preview_or_error, wdk_step_id)
    return with_summary(
        sample,
        f"{len(sample.records)} sample records from step {wdk_step_id}",
        ctx=ctx,
    )
