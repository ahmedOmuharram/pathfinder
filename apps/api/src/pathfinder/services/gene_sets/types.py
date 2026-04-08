"""Gene Set data model."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

GeneSetSource = Literal["strategy", "paste", "upload", "derived", "saved"]


@dataclass
class GeneSet:
    """A named collection of gene IDs for analysis."""

    id: str
    name: str
    site_id: str
    gene_ids: list[str]
    source: GeneSetSource
    user_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    wdk_strategy_id: int | None = None
    wdk_step_id: int | None = None
    search_name: str | None = None
    record_type: str | None = None
    parameters: dict[str, str] | None = None
    parent_set_ids: list[str] = field(default_factory=list)
    operation: str | None = None  # "intersect" | "union" | "minus"
    step_count: int = 1
