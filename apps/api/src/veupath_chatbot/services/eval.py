"""Thesis evaluation service.

Business logic for materializing gold strategies and fetching gene IDs.
The transport layer (``transport.http.routers.evaluation``) is a thin HTTP
adapter that delegates to this module.
"""

from dataclasses import dataclass
from typing import Any

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKRecordInstance
from veupath_chatbot.platform.logging import get_logger
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
    wdk_strategy_id = created.id

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
    strategy = await api.get_strategy(projection.wdk_strategy_id)
    return await fetch_all_gene_ids(api, strategy.root_step_id)


async def fetch_all_gene_ids(
    api: Any,
    step_id: int,
    batch_size: int = 1000,
) -> list[str]:
    """Fetch all gene IDs from a WDK step using paginated standard report."""
    all_ids: list[str] = []
    offset = 0

    while True:
        answer = await api.get_step_answer(
            step_id,
            attributes=["primary_key"],
            pagination={"offset": offset, "numRecords": batch_size},
        )

        records = answer.records
        if not records:
            break

        for record in records:
            gene_id = extract_gene_id(record)
            if gene_id:
                all_ids.append(gene_id)

        offset += len(records)
        if offset >= answer.meta.total_count:
            break

    return all_ids


def extract_gene_id(record: WDKRecordInstance) -> str | None:
    """Extract gene ID from a WDK record's primary key."""
    for part in record.id:
        name = part.get("name", "")
        value = part.get("value", "")
        if name in ("source_id", "gene_source_id") and value:
            return str(value)
    if record.id:
        return str(record.id[0].get("value", "")) or None
    return None
