from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from langgraph.store.base import Item, SearchItem
from langgraph.store.postgres.aio import AsyncPostgresStore

from pathfinder.ai.memory.embedding import format_embedded_string
from pathfinder.ai.memory.schemas import MemoryKind, MemoryValue
from pathfinder.integrations.embeddings.prefixes import SEARCH_QUERY_PREFIX


@dataclass(frozen=True)
class StoredMemory:
    """Memory as seen by callers — carries the storage key + optional score.

    ``score`` is only populated by :meth:`MemoryStore.semantic_search` (pulled
    from the HNSW index via ``Item.score``). Both ``list_all`` and ``get``
    leave it as ``None``.
    """

    key: str
    value: MemoryValue
    score: float | None = None


@dataclass(frozen=True)
class MemoryStore:
    """High-level API over LangGraph AsyncPostgresStore.

    Keys are auto-generated UUIDs unless caller supplies one. Namespaces are
    ``("user", user_id, kind)``. The stored payload is the raw
    :class:`MemoryValue` serialisation — the backing
    :class:`AsyncPostgresStore` embeds the fields configured in
    ``lifespan_memory_store`` (kind, name, tags, summary).
    """

    store: AsyncPostgresStore

    @staticmethod
    def _ns(user_id: UUID, kind: MemoryKind) -> tuple[str, str, str]:
        return ("user", str(user_id), kind)

    async def put(
        self,
        *,
        user_id: UUID,
        value: MemoryValue,
        key: str | None = None,
    ) -> str:
        mem_key = key or str(uuid4())
        payload = _dump_for_store(value)
        await self.store.aput(self._ns(user_id, value.kind), mem_key, payload)
        return mem_key

    async def get(
        self,
        *,
        user_id: UUID,
        kind: MemoryKind,
        key: str,
    ) -> StoredMemory | None:
        item = await self.store.aget(self._ns(user_id, kind), key)
        return _to_stored_get(item)

    async def delete(
        self,
        *,
        user_id: UUID,
        kind: MemoryKind,
        key: str,
    ) -> None:
        await self.store.adelete(self._ns(user_id, kind), key)

    async def list_all(
        self,
        *,
        user_id: UUID,
        kind: MemoryKind,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredMemory]:
        items = await self.store.asearch(
            self._ns(user_id, kind),
            query=None,
            limit=limit,
            offset=offset,
        )
        return [_to_stored_search(i) for i in items]

    async def semantic_search(
        self,
        *,
        user_id: UUID,
        kind: MemoryKind,
        query: str,
        top_k: int = 8,
    ) -> list[StoredMemory]:
        items = await self.store.asearch(
            self._ns(user_id, kind),
            query=f"{SEARCH_QUERY_PREFIX}{query}",
            limit=top_k,
        )
        return [_to_stored_search(i) for i in items]


def _dump_for_store(value: MemoryValue) -> dict[str, object]:
    """Serialise MemoryValue with a single synthetic field for embedding.

    LangGraph's store embeds one vector per configured ``fields`` key per
    item. Listing the raw kind/name/tags/summary as separate fields would
    cost 4x per put — instead we write the concatenated string to
    ``_embed_text`` and point the index config at that single key. The
    synthetic key is popped on read so it never leaks into
    :class:`MemoryValue`.
    """
    payload = value.model_dump(mode="json")
    payload["_embed_text"] = format_embedded_string(value)
    return payload


def _to_stored_get(item: Item | None) -> StoredMemory | None:
    """Convert a plain ``Item`` (from ``aget``) — no score populated."""
    if item is None:
        return None
    return StoredMemory(
        key=item.key,
        value=_parse_memory(item.value),
        score=None,
    )


def _to_stored_search(item: SearchItem) -> StoredMemory:
    """Convert a ``SearchItem`` (from ``asearch``) — carries the HNSW score."""
    return StoredMemory(
        key=item.key,
        value=_parse_memory(item.value),
        score=item.score,
    )


def _parse_memory(raw_value: dict[str, object]) -> MemoryValue:
    payload = dict(raw_value)
    payload.pop("_embed_text", None)
    return MemoryValue.model_validate(payload)
