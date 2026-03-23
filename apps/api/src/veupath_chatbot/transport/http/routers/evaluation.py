"""Thesis evaluation endpoints - materialize gold strategies and fetch gene IDs.

Thin HTTP adapter; all business logic lives in
``veupath_chatbot.services.eval``.

Read-only from the application's perspective (creates WDK strategies but does
not affect PathFinder's own data).  Used by thesis/eval/scripts/ only.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.eval import (
    build_gold_strategy,
    fetch_strategy_gene_ids,
)
from veupath_chatbot.transport.http.deps import CurrentUser, StreamRepo

router = APIRouter(prefix="/api/v1/eval", tags=["eval"])
logger = get_logger(__name__)


class BuildGoldRequest(BaseModel):
    """Request to materialize a gold strategy AST on WDK and return gene IDs."""

    gold_id: str = Field(alias="goldId")
    site_id: str = Field(alias="siteId")
    record_type: str = Field(default="gene", alias="recordType")
    step_tree: dict[str, Any] = Field(alias="stepTree")

    model_config = {"populate_by_name": True}


class BuildGoldResponse(BaseModel):
    gold_id: str = Field(alias="goldId")
    wdk_strategy_id: int = Field(alias="wdkStrategyId")
    root_step_id: int = Field(alias="rootStepId")
    estimated_size: int = Field(alias="estimatedSize")
    gene_ids: list[str] = Field(alias="geneIds")

    model_config = {"populate_by_name": True}


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
    )
    return BuildGoldResponse(
        goldId=result.gold_id,
        wdkStrategyId=result.wdk_strategy_id,
        rootStepId=result.root_step_id,
        estimatedSize=len(result.gene_ids),
        geneIds=result.gene_ids,
    )


class FetchGeneIdsRequest(BaseModel):
    """Fetch gene IDs from an existing PathFinder strategy."""

    strategy_id: str = Field(alias="strategyId")
    site_id: str = Field(alias="siteId")

    model_config = {"populate_by_name": True}


@router.post("/strategy-gene-ids")
async def get_strategy_gene_ids(
    request: FetchGeneIdsRequest,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> dict[str, Any]:
    """Fetch all gene IDs from a PathFinder strategy's WDK root step."""
    projection = await stream_repo.get_projection(UUID(request.strategy_id))
    if not projection or not projection.wdk_strategy_id:
        return {"geneIds": [], "error": "No WDK strategy linked"}

    api = get_strategy_api(request.site_id)
    gene_ids = await fetch_strategy_gene_ids(api=api, projection=projection)

    if not gene_ids:
        return {"geneIds": [], "error": "No gene IDs found"}
    return {"geneIds": gene_ids, "estimatedSize": len(gene_ids)}
