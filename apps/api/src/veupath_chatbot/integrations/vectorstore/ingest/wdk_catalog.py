from __future__ import annotations

import argparse
import asyncio
import os

from qdrant_client import AsyncQdrantClient
from veupath_chatbot.integrations.embeddings.openai_embeddings import (
    OpenAIEmbeddings,
    embed_one,
)
from veupath_chatbot.integrations.vectorstore.collections import (
    WDK_RECORD_TYPES_V1,
    WDK_SEARCHES_V1,
)
from veupath_chatbot.integrations.vectorstore.ingest.wdk_fetch import (
    fetch_record_types_and_searches,
    fetch_search_details,
)
from veupath_chatbot.integrations.vectorstore.ingest.wdk_index import (
    filter_existing_record_types,
    filter_existing_searches,
    run_search_indexing_pipeline,
    upsert_record_type_docs,
)
from veupath_chatbot.integrations.vectorstore.ingest.wdk_transform import (
    _unwrap_search_data,
    build_record_type_doc,
    build_search_doc,
)
from veupath_chatbot.integrations.vectorstore.qdrant_store import QdrantStore
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject

logger = get_logger(__name__)


async def ingest_site(
    *,
    site_id: str,
    store: QdrantStore,
    qdrant_client: AsyncQdrantClient,
    embedder: OpenAIEmbeddings,
    concurrency: int,
    batch_size: int,
    skip_existing: bool,
) -> None:
    router = get_site_router()
    client = router.get_client(site_id)

    raw_record_types, searches_to_fetch = await fetch_record_types_and_searches(client)

    record_type_docs: JSONArray = []
    for rt in raw_record_types:
        doc = build_record_type_doc(site_id, rt)
        if doc is not None:
            record_type_docs.append(doc)

    if skip_existing:
        record_type_docs = await filter_existing_record_types(
            qdrant_client, record_type_docs, site_id
        )
        searches_to_fetch = await filter_existing_searches(
            qdrant_client, searches_to_fetch, site_id
        )

    await upsert_record_type_docs(store, embedder, record_type_docs)

    async def make_doc(rt_name: str, s: JSONObject) -> tuple[JSONObject | None, bool]:
        if not isinstance(s, dict):
            return None, False
        if s.get("isInternal", False):
            return None, False
        search_name = str(s.get("urlSegment") or s.get("name") or "").strip()
        if not search_name:
            return None, False

        summary_unwrapped = _unwrap_search_data(s if isinstance(s, dict) else {})
        details_unwrapped, details_error = await fetch_search_details(
            client, rt_name, search_name, summary_unwrapped
        )
        doc = build_search_doc(
            site_id, rt_name, s, details_unwrapped, details_error, client.base_url
        )
        return doc, details_error is not None

    await run_search_indexing_pipeline(
        searches_to_fetch=searches_to_fetch,
        make_doc=make_doc,
        store=store,
        embedder=embedder,
        concurrency=concurrency,
        batch_size=batch_size,
        site_id=site_id,
    )


async def ingest_wdk_catalog(
    *,
    sites: list[str] | None,
    reset: bool = False,
    skip_existing: bool = True,
    batch_size: int = 64,
) -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("openai_api_key is required for embeddings ingestion")

    store = QdrantStore.from_settings()
    dim = len(await embed_one(text="dimension probe", model=settings.embeddings_model))

    if reset:
        reset_client = AsyncQdrantClient(
            url=store.url,
            api_key=store.api_key,
            timeout=int(store.timeout_seconds)
            if store.timeout_seconds is not None
            else None,
        )
        for name in (WDK_SEARCHES_V1, WDK_RECORD_TYPES_V1):
            if await reset_client.collection_exists(collection_name=name):
                await reset_client.delete_collection(collection_name=name)

    await store.ensure_collection(name=WDK_RECORD_TYPES_V1, vector_size=dim)
    await store.ensure_collection(name=WDK_SEARCHES_V1, vector_size=dim)

    embedder = OpenAIEmbeddings(model=settings.embeddings_model)
    concurrency = max(1, int(os.cpu_count() or 1) * 10)
    logger.info(
        "WDK ingest starting",
        concurrency=concurrency,
        batch_size=batch_size,
        skip_existing=skip_existing,
    )

    router = get_site_router()
    all_sites = [s.id for s in router.list_sites()]
    selected = all_sites if not sites else [s for s in all_sites if s in set(sites)]

    qdrant_client = AsyncQdrantClient(
        url=store.url,
        api_key=store.api_key,
        timeout=int(store.timeout_seconds)
        if store.timeout_seconds is not None
        else None,
    )
    try:
        for site_id in selected:
            logger.info("WDK ingest site", siteId=site_id)
            await ingest_site(
                site_id=site_id,
                store=store,
                qdrant_client=qdrant_client,
                embedder=embedder,
                concurrency=concurrency,
                batch_size=max(8, int(batch_size)),
                skip_existing=bool(skip_existing) and (not bool(reset)),
            )
    finally:
        await qdrant_client.close()


def _parse_sites(value: str) -> list[str] | None:
    v = (value or "").strip()
    if not v or v == "all":
        return None
    return [s.strip() for s in v.split(",") if s.strip()]


async def _cli_async(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sites", default="all", help="Comma-separated site IDs or 'all' (default)."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and recreate target collections before ingest.",
    )
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip record types/searches that already exist in Qdrant (default: true).",
    )
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args(argv)

    await ingest_wdk_catalog(
        sites=_parse_sites(args.sites),
        reset=bool(args.reset),
        skip_existing=bool(args.skip_existing),
        batch_size=int(args.batch_size),
    )


def main(argv: list[str] | None = None) -> None:
    asyncio.run(_cli_async(argv))


if __name__ == "__main__":
    main()
