from __future__ import annotations

from assistant_core.memory.schemas import MemoryValue
from assistant_core.platform.pydantic_base import CamelModel


class MemoryItem(CamelModel):
    key: str
    value: MemoryValue


class MemoryListResponse(CamelModel):
    """Paginated list, grouped by namespace.

    ``page_size`` and ``offset`` echo the query params. ``has_more`` is
    ``True`` when at least one namespace returned a full page (i.e. more
    rows likely exist at the next offset). Clients use this to decide
    whether to render a "load more" affordance without an additional
    count query.
    """

    gene_sets: list[MemoryItem]
    strategies: list[MemoryItem]
    preferences: list[MemoryItem]
    knowledge: list[MemoryItem]
    cases: list[MemoryItem]
    page_size: int
    offset: int
    has_more: bool


class MemoryEditRequest(CamelModel):
    name: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    content: dict[str, object] | None = None
    auto_retrieve: bool | None = None


class MemorySearchResponse(CamelModel):
    hits: list[MemoryItem]
