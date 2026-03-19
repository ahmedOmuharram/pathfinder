"""Thesis evaluation endpoints — materialize gold strategies and fetch gene IDs.

Read-only from the application's perspective (creates WDK strategies but does
not affect PathFinder's own data).  Used by thesis/eval/scripts/ only.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
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
    result_count: int = Field(alias="resultCount")
    gene_ids: list[str] = Field(alias="geneIds")

    model_config = {"populate_by_name": True}


@router.post("/build-gold", response_model=BuildGoldResponse)
async def build_gold_strategy(
    request: BuildGoldRequest,
    user_id: CurrentUser,
) -> BuildGoldResponse:
    """Materialize a gold strategy AST on WDK and fetch all result gene IDs.

    1. Recursively creates WDK steps from the step tree.
    2. Wraps them in a WDK strategy.
    3. Fetches all gene IDs from the root step via standard report.
    4. Returns the gene IDs plus WDK IDs.
    """
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
    from veupath_chatbot.services.experiment.helpers import extract_wdk_id
    from veupath_chatbot.services.experiment.materialization import (
        _materialize_step_tree,
    )

    api = get_strategy_api(request.site_id)

    # 1. Materialize step tree → real WDK steps
    root_tree = await _materialize_step_tree(
        api, request.step_tree, request.record_type, site_id=request.site_id
    )
    root_step_id = root_tree.step_id

    # 2. Create WDK strategy
    created = await api.create_strategy(
        step_tree=root_tree,
        name=f"gold:{request.gold_id}",
        description=f"Gold strategy: {request.gold_id}",
        is_saved=False,
    )
    wdk_strategy_id = extract_wdk_id(created)
    if wdk_strategy_id is None:
        raise ValueError(f"WDK did not return a strategy ID for '{request.gold_id}'")

    logger.info(
        "Built gold strategy on WDK",
        gold_id=request.gold_id,
        wdk_strategy_id=wdk_strategy_id,
        root_step_id=root_step_id,
    )

    # 3. Fetch ALL gene IDs from root step via standard report (paginated)
    gene_ids = await _fetch_all_gene_ids(api, root_step_id)

    return BuildGoldResponse(
        goldId=request.gold_id,
        wdkStrategyId=wdk_strategy_id,
        rootStepId=root_step_id,
        resultCount=len(gene_ids),
        geneIds=gene_ids,
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
    from uuid import UUID

    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    projection = await stream_repo.get_projection(UUID(request.strategy_id))
    if not projection or not projection.wdk_strategy_id:
        return {"geneIds": [], "error": "No WDK strategy linked"}

    api = get_strategy_api(request.site_id)
    await api._ensure_session()  # noqa: SLF001 — resolve WDK user ID

    # Get root step ID from WDK strategy
    wdk_strat = await api.client.get(
        f"/users/{api.user_id}/strategies/{projection.wdk_strategy_id}"
    )
    if not isinstance(wdk_strat, dict):
        return {"geneIds": [], "error": "Could not fetch WDK strategy"}

    root_step_id = wdk_strat.get("rootStepId")
    if not root_step_id:
        # Try stepTree
        step_tree = wdk_strat.get("stepTree", {})
        root_step_id = step_tree.get("stepId") if isinstance(step_tree, dict) else None

    if not root_step_id:
        return {"geneIds": [], "error": "No root step ID found"}

    raw_id = root_step_id
    step_id_int = int(raw_id) if isinstance(raw_id, (int, float, str)) else 0
    gene_ids = await _fetch_all_gene_ids(api, step_id_int)
    return {"geneIds": gene_ids, "resultCount": len(gene_ids)}


async def _fetch_all_gene_ids(
    api: Any,
    step_id: int,
    batch_size: int = 1000,
) -> list[str]:
    """Fetch all gene IDs from a WDK step using paginated standard report."""
    all_ids: list[str] = []
    offset = 0

    while True:
        answer: JSONObject = await api.get_step_answer(
            step_id,
            attributes=["primary_key"],
            pagination={"offset": offset, "numRecords": batch_size},
        )

        records = answer.get("records")
        if not isinstance(records, list) or not records:
            break

        for record in records:
            if not isinstance(record, dict):
                continue
            gene_id = _extract_gene_id(record)
            if gene_id:
                all_ids.append(gene_id)

        meta = answer.get("meta")
        raw_total = meta.get("totalCount", 0) if isinstance(meta, dict) else 0
        total_count = int(raw_total) if isinstance(raw_total, (int, float)) else 0

        offset += len(records)
        if offset >= total_count:
            break

    return all_ids


def _extract_gene_id(record: JSONObject) -> str | None:
    """Extract gene ID from a WDK record's primary key."""
    pk = record.get("id")
    if isinstance(pk, list):
        for part in pk:
            if isinstance(part, dict):
                name = part.get("name", "")
                value = part.get("value", "")
                # Gene records use "source_id" or "gene_source_id"
                if name in ("source_id", "gene_source_id") and value:
                    return str(value)
        # Fallback: use first part's value
        if pk and isinstance(pk[0], dict):
            return str(pk[0].get("value", ""))
    return None
