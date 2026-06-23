from __future__ import annotations

from uuid import UUID

from pydantic import TypeAdapter

from pathfinder.ai.memory.schemas import MemoryKind
from pathfinder.ai.memory.store import MemoryStore

_KIND_ADAPTER: TypeAdapter[MemoryKind] = TypeAdapter(MemoryKind)
_NAMESPACE_PAGE = 10_000


async def reembed_all_memories(store: MemoryStore) -> int:
    """Re-embed every stored memory in place with the current embed format.

    Reads each memory and re-puts it under the same key, regenerating the
    ``_embed_text`` field via :func:`embedding.format_embedded_string`. Run
    after the embedding scheme changes (e.g. adding nomic prefixes) so the
    persisted vectors match how queries are now embedded. Returns the number
    of memories re-embedded.
    """
    namespaces = await store.store.alist_namespaces(
        prefix=("user",), limit=_NAMESPACE_PAGE
    )
    count = 0
    for namespace in namespaces:
        _, user_id_raw, kind_raw = namespace
        user_id = UUID(user_id_raw)
        kind = _KIND_ADAPTER.validate_python(kind_raw)
        for stored in await store.list_all(
            user_id=user_id, kind=kind, limit=_NAMESPACE_PAGE
        ):
            await store.put(user_id=user_id, value=stored.value, key=stored.key)
            count += 1
    return count
