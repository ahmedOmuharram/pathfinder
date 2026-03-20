"""Thesis evaluation service.

Business logic for materializing gold strategies and fetching gene IDs.
The transport layer (``transport.http.routers.evaluation``) is a thin HTTP
adapter that delegates to this module.
"""

from dataclasses import dataclass
from typing import Any

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.helpers import extract_wdk_id
from veupath_chatbot.services.experiment.materialization import (
    _materialize_step_tree,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class GoldStrategyResult:
    """Result of materializing a gold strategy on WDK."""

    gold_id: str
    wdk_strategy_id: int
    root_step_id: int
    gene_ids: list[str]


async def build_gold_strategy(
    *,
    gold_id: str,
    site_id: str,
    record_type: str,
    step_tree: dict[str, Any],
) -> GoldStrategyResult:
    """Materialize a gold strategy AST on WDK and fetch all result gene IDs.

    1. Recursively creates WDK steps from the step tree.
    2. Wraps them in a WDK strategy.
    3. Fetches all gene IDs from the root step via standard report.
    4. Returns the gene IDs plus WDK IDs.
    """
    api = get_strategy_api(site_id)

    root_tree = await _materialize_step_tree(
        api, step_tree, record_type, site_id=site_id
    )
    root_step_id = root_tree.step_id

    created = await api.create_strategy(
        step_tree=root_tree,
        name=f"gold:{gold_id}",
        description=f"Gold strategy: {gold_id}",
        is_saved=False,
    )
    wdk_strategy_id = extract_wdk_id(created)
    if wdk_strategy_id is None:
        msg = f"WDK did not return a strategy ID for '{gold_id}'"
        raise ValueError(msg)

    logger.info(
        "Built gold strategy on WDK",
        gold_id=gold_id,
        wdk_strategy_id=wdk_strategy_id,
        root_step_id=root_step_id,
    )

    gene_ids = await fetch_all_gene_ids(api, root_step_id)

    return GoldStrategyResult(
        gold_id=gold_id,
        wdk_strategy_id=wdk_strategy_id,
        root_step_id=root_step_id,
        gene_ids=gene_ids,
    )


async def fetch_strategy_gene_ids(
    *,
    api: Any,
    projection: Any,
) -> list[str]:
    """Fetch all gene IDs from a strategy's WDK root step.

    :param api: StrategyAPI instance for the site.
    :param projection: StreamProjection with ``wdk_strategy_id``.
    :returns: List of gene ID strings.
    """
    await api._ensure_session()

    wdk_strat: JSONObject = await api.client.get(
        f"/users/{api.user_id}/strategies/{projection.wdk_strategy_id}"
    )
    if not isinstance(wdk_strat, dict):
        return []

    root_step_id = extract_root_step_id(wdk_strat)
    if not root_step_id:
        return []

    step_id_int = (
        int(root_step_id) if isinstance(root_step_id, (int, float, str)) else 0
    )
    return await fetch_all_gene_ids(api, step_id_int)


def extract_root_step_id(wdk_strat: JSONObject) -> object:
    """Extract root step ID from a WDK strategy response."""
    root_step_id = wdk_strat.get("rootStepId")
    if root_step_id:
        return root_step_id
    step_tree = wdk_strat.get("stepTree", {})
    return step_tree.get("stepId") if isinstance(step_tree, dict) else None


async def fetch_all_gene_ids(
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
            gene_id = extract_gene_id(record)
            if gene_id:
                all_ids.append(gene_id)

        meta = answer.get("meta")
        raw_total = meta.get("totalCount", 0) if isinstance(meta, dict) else 0
        total_count = int(raw_total) if isinstance(raw_total, (int, float)) else 0

        offset += len(records)
        if offset >= total_count:
            break

    return all_ids


def extract_gene_id(record: JSONObject) -> str | None:
    """Extract gene ID from a WDK record's primary key."""
    pk = record.get("id")
    if isinstance(pk, list):
        for part in pk:
            if isinstance(part, dict):
                name = part.get("name", "")
                value = part.get("value", "")
                if name in ("source_id", "gene_source_id") and value:
                    return str(value)
        if pk and isinstance(pk[0], dict):
            return str(pk[0].get("value", ""))
    return None
