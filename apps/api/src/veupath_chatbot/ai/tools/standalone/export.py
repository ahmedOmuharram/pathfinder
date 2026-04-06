"""Standalone export tools for pydantic-ai agents.

Provides:
- ``export_gene_set`` -- export a gene set as a downloadable file
"""

from typing import Literal
from uuid import UUID

from pydantic_ai import RunContext

from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.tools.standalone._export_models import (
    ExportResultResponse,
    GeneSetSummaryItem,
)
from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.tool_errors import ToolErrorPayload, tool_error
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.export import get_export_service
from veupath_chatbot.services.gene_sets.store import get_gene_set_store


async def _available_gene_sets(
    site_id: str,
    user_id: UUID | None,
) -> list[JSONObject]:
    """Return summary of available gene sets for error messages."""
    store = get_gene_set_store()
    if user_id is not None:
        sets = await store.alist_for_user(user_id, site_id=site_id)
    else:
        sets = await store.alist_all(site_id=site_id)
    return [
        GeneSetSummaryItem(
            id=gs.id, name=gs.name, gene_count=len(gs.gene_ids)
        ).model_dump(by_alias=True, exclude_none=True, mode="json")
        for gs in sets[:10]
    ]


async def export_gene_set(
    ctx: RunContext[AgentDeps],
    gene_set_id: str,
    output_format: str = "csv",
) -> ExportResultResponse | ToolErrorPayload:
    """Export a gene set as a downloadable CSV or TXT file.

    Returns a download URL that the user can click to download the file.
    The URL expires after 10 minutes.

    Args:
        gene_set_id: PathFinder gene set ID.
        output_format: Export format: csv or txt.
    """
    if output_format not in ("csv", "txt"):
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "format must be 'csv' or 'txt'.",
            format=output_format,
        )

    deps = ctx.deps
    store = get_gene_set_store()
    gs = await store.aget(gene_set_id)
    if gs is None:
        available: list[JSONValue] = list(
            await _available_gene_sets(deps.site_id, deps.user_id)
        )
        return tool_error(
            ErrorCode.NOT_FOUND,
            f"Gene set not found: {gene_set_id}. Use one of the available IDs below.",
            gene_set_id=gene_set_id,
            availableGeneSets=available,
        )

    svc = get_export_service()
    fmt: Literal["csv", "txt"] = "txt" if output_format == "txt" else "csv"
    result = await svc.export_gene_set(gs, fmt)
    return ExportResultResponse(
        download_url=result.url,
        filename=result.filename,
        format=output_format,
        item_count=len(gs.gene_ids),
        expires_in_seconds=result.expires_in_seconds,
    )
