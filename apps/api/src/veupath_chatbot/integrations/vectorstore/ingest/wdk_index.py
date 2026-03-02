from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, cast

from qdrant_client import AsyncQdrantClient
from veupath_chatbot.integrations.embeddings.openai_embeddings import OpenAIEmbeddings
from veupath_chatbot.integrations.vectorstore.collections import (
    WDK_RECORD_TYPES_V1,
    WDK_SEARCHES_V1,
)
from veupath_chatbot.integrations.vectorstore.ingest.utils import existing_point_ids
from veupath_chatbot.integrations.vectorstore.qdrant_store import (
    QdrantStore,
    point_uuid,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject

logger = get_logger(__name__)


async def filter_existing_record_types(
    qdrant_client: AsyncQdrantClient,
    record_type_docs: JSONArray,
    site_id: str,
) -> JSONArray:
    rt_ids: list[str] = []
    for d in record_type_docs:
        if isinstance(d, dict):
            id_value = d.get("id")
            if id_value is not None:
                rt_ids.append(str(id_value))
    existing_rts = await existing_point_ids(
        qdrant_client=qdrant_client, collection=WDK_RECORD_TYPES_V1, ids=rt_ids
    )
    if existing_rts:
        before = len(record_type_docs)
        filtered_docs: JSONArray = []
        for d in record_type_docs:
            if isinstance(d, dict):
                id_value = d.get("id")
                if id_value is not None and str(id_value) not in existing_rts:
                    filtered_docs.append(d)
        record_type_docs = filtered_docs
        skipped = before - len(record_type_docs)
        if skipped:
            logger.info("WDK record types skipped", siteId=site_id, skipped=skipped)

    return record_type_docs


async def filter_existing_searches(
    qdrant_client: AsyncQdrantClient,
    searches_to_fetch: list[tuple[str, JSONObject]],
    site_id: str,
) -> list[tuple[str, JSONObject]]:
    enriched: list[tuple[str, JSONObject, str]] = []
    for rt_name, s in searches_to_fetch:
        if not isinstance(s, dict):
            continue
        if s.get("isInternal", False):
            continue
        search_name = str(s.get("urlSegment") or s.get("name") or "").strip()
        if not search_name:
            continue
        enriched.append((rt_name, s, point_uuid(f"{site_id}:{rt_name}:{search_name}")))

    search_ids = [sid for _, _, sid in enriched]
    existing_searches = await existing_point_ids(
        qdrant_client=qdrant_client, collection=WDK_SEARCHES_V1, ids=search_ids
    )
    if existing_searches:
        before = len(enriched)
        enriched = [t for t in enriched if t[2] not in existing_searches]
        skipped = before - len(enriched)
        if skipped:
            logger.info("WDK searches skipped", siteId=site_id, skipped=skipped)

    return [(rt_name, s) for rt_name, s, _ in enriched]


async def upsert_record_type_docs(
    store: QdrantStore,
    embedder: OpenAIEmbeddings,
    record_type_docs: JSONArray,
) -> None:
    if not record_type_docs:
        return
    texts: list[str] = []
    valid_docs: list[JSONObject] = []
    for d in record_type_docs:
        if isinstance(d, dict):
            text_value = d.get("text")
            if isinstance(text_value, str):
                texts.append(text_value)
                valid_docs.append(d)
    vectors = await embedder.embed_texts(texts)
    await store.upsert(
        collection=WDK_RECORD_TYPES_V1,
        points=[
            cast(
                Any,
                {"id": d.get("id"), "vector": v, "payload": d.get("payload", {})},
            )
            for d, v in zip(valid_docs, vectors, strict=True)
        ],
    )


async def upsert_search_docs_batch(
    store: QdrantStore,
    embedder: OpenAIEmbeddings,
    buffered: JSONArray,
) -> None:
    if not buffered:
        return
    texts: list[str] = []
    valid_docs: list[JSONObject] = []
    for d in buffered:
        if isinstance(d, dict):
            text_value = d.get("text")
            if isinstance(text_value, str):
                texts.append(text_value)
                valid_docs.append(d)
    vectors = await embedder.embed_texts(texts)
    await store.upsert(
        collection=WDK_SEARCHES_V1,
        points=[
            cast(
                Any,
                {
                    "id": d.get("id"),
                    "vector": v,
                    "payload": d.get("payload", {}),
                },
            )
            for d, v in zip(valid_docs, vectors, strict=True)
        ],
    )


async def run_search_indexing_pipeline(
    *,
    searches_to_fetch: list[tuple[str, JSONObject]],
    make_doc: Callable[[str, JSONObject], Awaitable[tuple[JSONObject | None, bool]]],
    store: QdrantStore,
    embedder: OpenAIEmbeddings,
    concurrency: int,
    batch_size: int,
    site_id: str,
) -> None:
    failed_details: int = 0
    jobs: asyncio.Queue[tuple[str, JSONObject] | None] = asyncio.Queue()
    docs: asyncio.Queue[JSONObject | None] = asyncio.Queue()

    async def worker() -> None:
        nonlocal failed_details
        while True:
            item = await jobs.get()
            if item is None:
                jobs.task_done()
                break
            rt_name, s = item
            try:
                doc, had_error = await make_doc(rt_name, s)
                if had_error:
                    failed_details += 1
                await docs.put(doc)
            finally:
                jobs.task_done()

    async def consumer() -> None:
        buffered: JSONArray = []
        while True:
            doc = await docs.get()
            if doc is None:
                docs.task_done()
                break
            buffered.append(doc)
            docs.task_done()
            if len(buffered) >= batch_size:
                await upsert_search_docs_batch(store, embedder, buffered)
                buffered.clear()

        if buffered:
            await upsert_search_docs_batch(store, embedder, buffered)

    consumer_task = asyncio.create_task(consumer())
    workers = [asyncio.create_task(worker()) for _ in range(max(1, int(concurrency)))]

    for rt_name, s in searches_to_fetch:
        await jobs.put((rt_name, s))
    for _ in workers:
        await jobs.put(None)

    await jobs.join()
    await docs.put(None)
    await consumer_task
    for w in workers:
        await w

    if failed_details:
        logger.warning(
            "WDK search details failed", siteId=site_id, failed=failed_details
        )
