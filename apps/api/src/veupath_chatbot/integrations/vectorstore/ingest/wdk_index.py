from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient

from veupath_chatbot.integrations.embeddings.openai_embeddings import OpenAIEmbeddings
from veupath_chatbot.integrations.vectorstore.collections import (
    WDK_RECORD_TYPES_V1,
    WDK_SEARCHES_V1,
)
from veupath_chatbot.integrations.vectorstore.ingest.pipeline import (
    run_concurrent_pipeline,
)
from veupath_chatbot.integrations.vectorstore.ingest.utils import (
    embed_and_upsert,
    existing_point_ids,
)
from veupath_chatbot.integrations.vectorstore.qdrant_store import (
    QdrantStore,
    point_uuid,
)
from veupath_chatbot.integrations.veupathdb.param_utils import wdk_entity_name
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue

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
        search_name = wdk_entity_name(s)
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


async def _upsert_docs_batch(
    store: QdrantStore,
    embedder: OpenAIEmbeddings,
    collection: str,
    docs: JSONArray,
) -> None:
    if not docs:
        return
    ids: list[str | JSONValue] = []
    texts: list[str] = []
    payloads: list[JSONObject] = []
    for d in docs:
        if isinstance(d, dict):
            text_value = d.get("text")
            if isinstance(text_value, str):
                ids.append(d.get("id"))
                texts.append(text_value)
                payload_raw = d.get("payload")
                payloads.append(payload_raw if isinstance(payload_raw, dict) else {})
    await embed_and_upsert(
        store=store,
        embedder=embedder,
        collection=collection,
        ids=ids,
        texts=texts,
        payloads=payloads,
    )


async def upsert_record_type_docs(
    store: QdrantStore,
    embedder: OpenAIEmbeddings,
    record_type_docs: JSONArray,
) -> None:
    await _upsert_docs_batch(store, embedder, WDK_RECORD_TYPES_V1, record_type_docs)


async def upsert_search_docs_batch(
    store: QdrantStore,
    embedder: OpenAIEmbeddings,
    buffered: JSONArray,
) -> None:
    await _upsert_docs_batch(store, embedder, WDK_SEARCHES_V1, buffered)


@dataclass
class SearchIndexingConfig:
    """Configuration bundle for :func:`run_search_indexing_pipeline`."""

    store: QdrantStore
    embedder: OpenAIEmbeddings
    concurrency: int
    batch_size: int
    site_id: str


async def run_search_indexing_pipeline(
    *,
    searches_to_fetch: list[tuple[str, JSONObject]],
    make_doc: Callable[[str, JSONObject], Awaitable[tuple[JSONObject | None, bool]]],
    config: SearchIndexingConfig,
) -> None:
    failed_details: int = 0

    async def process(item: tuple[str, JSONObject]) -> JSONObject | None:
        nonlocal failed_details
        rt_name, s = item
        doc, had_error = await make_doc(rt_name, s)
        if had_error:
            failed_details += 1
        return doc

    async def flush(batch: list[JSONObject]) -> None:
        await upsert_search_docs_batch(config.store, config.embedder, list(batch))

    await run_concurrent_pipeline(
        items=searches_to_fetch,
        process_fn=process,
        flush_fn=flush,
        concurrency=config.concurrency,
        batch_size=config.batch_size,
    )

    if failed_details:
        logger.warning(
            "WDK search details failed",
            siteId=config.site_id,
            failed=failed_details,
        )
