"""Builders for the ``DataChunk``s that carry strategy telemetry to the
frontend as data parts on the assistant message."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel
from pydantic_ai.ui.vercel_ai.response_types import DataChunk

from pathfinder.platform.pydantic_base import CamelModel


def enrichment_results_event(
    *,
    task_id: UUID,
    gene_set_id: str,
    gene_set_name: str,
    gene_count: int,
    results: list[dict[str, object]],
    downloads: dict[str, str | int] | None = None,
) -> DataChunk:
    return DataChunk(
        type="data-enrichment-results",
        data={
            "taskId": str(task_id),
            "geneSetId": gene_set_id,
            "geneSetName": gene_set_name,
            "geneCount": gene_count,
            "results": results,
            "downloads": downloads,
        },
    )


class StrategyRevisionPayload(CamelModel):
    """Payload for the strategy-revision chunk. The revision is a fingerprint
    of the strategy that the turn describes.
    """

    revision: str


def strategy_revision_event(*, revision: str) -> DataChunk:
    return DataChunk(
        type="data-strategy-revision",
        data=StrategyRevisionPayload(revision=revision).model_dump(
            by_alias=True,
            mode="json",
        ),
    )


def ledger_update_event(*, ledger: BaseModel) -> DataChunk:
    """Report a snapshot of the investigation ledger."""
    return DataChunk(
        type="data-ledger-update",
        data=ledger.model_dump(by_alias=True, mode="json", exclude_none=True),
    )
