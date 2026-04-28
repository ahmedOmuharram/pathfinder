from __future__ import annotations

from typing import Any

from shared_py.pydantic_base import CamelModel


class EnrichmentResultsChunk(CamelModel):
    task_id: str
    gene_set_id: str
    gene_set_name: str
    gene_count: int
    results: list[dict[str, Any]]
    downloads: dict[str, str | int] | None = None
