from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from pathfinder.platform.pydantic_base import CamelModel

MemoryKind = Literal["gene_set", "strategy", "preference", "knowledge"]

TombstoneReason = Literal["user_deleted", "auto_pruned"]


class MemoryValue(CamelModel):
    kind: MemoryKind
    name: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    site_id: str | None = None
    content: dict[str, object]
    auto_retrieve: bool = True
    source_chat_id: UUID | None = None
    created_at: datetime
    last_used_at: datetime | None = None


class MemoryTombstone(CamelModel):
    user_id: UUID
    kind: MemoryKind
    content_hash: str
    deleted_at: datetime
    reason: TombstoneReason = "user_deleted"
