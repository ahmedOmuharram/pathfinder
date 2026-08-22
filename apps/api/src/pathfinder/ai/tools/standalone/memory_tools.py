"""LLM-callable memory tools: search_memory + remember."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic_ai.tools import RunContext

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.lead.memory_candidates import PRODUCT_MEMORY_KINDS
from pathfinder.assistant_core.memory.retrieval import rerank_by_hybrid_score
from pathfinder.assistant_core.memory.schemas import MemoryKind, MemoryValue
from pathfinder.assistant_core.memory.store import MemoryStore, StoredMemory


async def search_memory(
    ctx: RunContext[AgentDeps],
    query: str,
    kind: MemoryKind | None = None,
    top_k: int = 5,
) -> list[dict[str, object]]:
    """Search the user's cross-thread memory semantically.

    Use this when the user references prior work, asks "what did we do before",
    or when recalling past context would improve your answer.

    Distributes ``top_k`` across the four namespaces (or uses the full budget
    if ``kind`` is given), then reranks globally via the hybrid score so the
    most relevant hits across namespaces come first.
    """
    store_raw = ctx.deps.memory_store
    user_id = ctx.deps.user_id
    if store_raw is None or user_id is None:
        return []
    mem_store = MemoryStore(store=store_raw)
    kinds: tuple[str, ...] = (kind,) if kind is not None else PRODUCT_MEMORY_KINDS
    per_kind = max(1, top_k) if len(kinds) == 1 else max(1, top_k // len(kinds))

    all_hits: list[StoredMemory] = []
    for k in kinds:
        hits = await mem_store.semantic_search(
            user_id=user_id,
            kind=k,
            query=query,
            top_k=per_kind,
        )
        all_hits.extend(hits)
    reranked = rerank_by_hybrid_score(all_hits)
    return [stored.value.model_dump(mode="json") for stored in reranked[:top_k]]


async def remember(
    ctx: RunContext[AgentDeps],
    kind: MemoryKind,
    name: str,
    summary: str,
    content: dict[str, object],
    tags: list[str] | None = None,
) -> str:
    """Store an explicit memory for this user.

    Use for biological facts the user has taught you or preferences they've
    stated. Returns the storage key or an error string.
    """
    store_raw = ctx.deps.memory_store
    user_id = ctx.deps.user_id
    if store_raw is None or user_id is None:
        return "memory store unavailable"
    mem_store = MemoryStore(store=store_raw)
    value = MemoryValue(
        kind=kind,
        name=name,
        summary=summary,
        tags=tags or [],
        site_id=ctx.deps.site_id,
        content=content,
        created_at=datetime.now(UTC),
    )
    return await mem_store.put(user_id=user_id, value=value)
