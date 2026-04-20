"""Thesis evaluation endpoints - materialize gold strategies and fetch gene IDs.

Thin HTTP adapter; all business logic lives in
``pathfinder.services.eval``.

Read-only from the application's perspective (creates WDK strategies but does
not affect PathFinder's own data).  Used by thesis/eval/scripts/ only.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import Field

from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.eval import (
    build_gold_strategy,
    fetch_strategy_gene_ids,
)
from pathfinder.services.wdk import get_strategy_api
from pathfinder.transport.http.deps import ConversationRepo, CurrentUser

router = APIRouter(prefix="/api/v1/eval", tags=["eval"])
logger = get_logger(__name__)


class BuildGoldRequest(CamelModel):
    """Request to materialize a gold strategy AST on WDK and return gene IDs."""

    gold_id: str
    site_id: str
    record_type: str = Field(default="gene")
    step_tree: dict[str, Any]
    dataset_gene_ids: dict[str, list[str]] | None = Field(default=None)


class BuildGoldResponse(CamelModel):
    gold_id: str
    wdk_strategy_id: int
    root_step_id: int
    estimated_size: int
    gene_ids: list[str]
    conversation_id: str | None = Field(default=None)


@router.post("/build-gold", response_model=BuildGoldResponse)
async def build_gold_strategy_endpoint(
    request: BuildGoldRequest,
    user_id: CurrentUser,
) -> BuildGoldResponse:
    """Materialize a gold strategy AST on WDK and fetch all result gene IDs."""
    result = await build_gold_strategy(
        gold_id=request.gold_id,
        site_id=request.site_id,
        record_type=request.record_type,
        step_tree=request.step_tree,
        dataset_gene_ids=request.dataset_gene_ids,
        user_id=user_id,
    )
    return BuildGoldResponse(
        gold_id=result.gold_id,
        wdk_strategy_id=result.wdk_strategy_id,
        root_step_id=result.root_step_id,
        estimated_size=len(result.gene_ids),
        gene_ids=result.gene_ids,
        conversation_id=str(result.conversation_id) if result.conversation_id is not None else None,
    )


class FetchGeneIdsRequest(CamelModel):
    """Fetch gene IDs from an existing PathFinder strategy."""

    strategy_id: str
    site_id: str


@router.post("/strategy-gene-ids")
async def get_strategy_gene_ids(
    request: FetchGeneIdsRequest,
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> dict[str, Any]:
    """Fetch all gene IDs from a PathFinder strategy's WDK root step."""
    conversation = await conv_repo.get_by_id(UUID(request.strategy_id))
    if not conversation or not conversation.wdk_strategy_id:
        return {"geneIds": [], "error": "No WDK strategy linked"}

    api = get_strategy_api(request.site_id)
    gene_ids = await fetch_strategy_gene_ids(api=api, conversation=conversation)

    if not gene_ids:
        return {"geneIds": [], "error": "No gene IDs found"}
    return {"geneIds": gene_ids, "estimatedSize": len(gene_ids)}
