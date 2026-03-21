import argparse
import asyncio
import os
from dataclasses import dataclass

import httpx
from qdrant_client import AsyncQdrantClient

from veupath_chatbot.integrations.embeddings.openai_embeddings import OpenAIEmbeddings
from veupath_chatbot.integrations.vectorstore.bootstrap import get_embedding_dim
from veupath_chatbot.integrations.vectorstore.collections import (
    WDK_RECORD_TYPES_V1,
    WDK_SEARCHES_V1,
)
from veupath_chatbot.integrations.vectorstore.ingest.utils import parse_sites
from veupath_chatbot.integrations.vectorstore.ingest.wdk_fetch import (
    fetch_record_types_and_searches,
    fetch_search_details,
)
from veupath_chatbot.integrations.vectorstore.ingest.wdk_index import (
    SearchIndexingConfig,
    filter_existing_record_types,
    filter_existing_searches,
    run_search_indexing_pipeline,
    upsert_record_type_docs,
)
from veupath_chatbot.integrations.vectorstore.ingest.wdk_transform import (
    build_record_type_doc,
    build_search_doc,
)
from veupath_chatbot.integrations.vectorstore.qdrant_store import QdrantStore
from veupath_chatbot.integrations.veupathdb.param_utils import wdk_entity_name
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject

logger = get_logger(__name__)


@dataclass
class IngestSiteConfig:
    """Configuration bundle for :func:`ingest_site`."""

    site_id: str
    store: QdrantStore
    qdrant_client: AsyncQdrantClient
    embedder: OpenAIEmbeddings
    concurrency: int
    batch_size: int
    skip_existing: bool


async def ingest_site(cfg: IngestSiteConfig) -> None:
    router = get_site_router()
    client = router.get_client(cfg.site_id)

    raw_record_types, searches_to_fetch = await fetch_record_types_and_searches(client)

    record_type_docs: JSONArray = []
    for rt in raw_record_types:
        doc = build_record_type_doc(cfg.site_id, rt)
        if doc is not None:
            record_type_docs.append(doc)

    if cfg.skip_existing:
        record_type_docs = await filter_existing_record_types(
            cfg.qdrant_client, record_type_docs, cfg.site_id
        )
        searches_to_fetch = await filter_existing_searches(
            cfg.qdrant_client, searches_to_fetch, cfg.site_id
        )

    await upsert_record_type_docs(cfg.store, cfg.embedder, record_type_docs)

    async def make_doc(rt_name: str, s: JSONObject) -> tuple[JSONObject | None, bool]:
        if not isinstance(s, dict):
            return None, False
        full_name = s.get("fullName", "")
        if isinstance(full_name, str) and full_name.startswith("InternalQuestions."):
            return None, False
        search_name = wdk_entity_name(s)
        if not search_name:
            return None, False

        details_dict, details_error = await fetch_search_details(
            client, rt_name, search_name, s
        )
        doc = build_search_doc(
            cfg.site_id, rt_name, s, details_dict, details_error, client.base_url
        )
        return doc, details_error is not None

    indexing_config = SearchIndexingConfig(
        store=cfg.store,
        embedder=cfg.embedder,
        concurrency=cfg.concurrency,
        batch_size=cfg.batch_size,
        site_id=cfg.site_id,
    )
    await run_search_indexing_pipeline(
        searches_to_fetch=searches_to_fetch,
        make_doc=make_doc,
        config=indexing_config,
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
        msg = "openai_api_key is required for embeddings ingestion"
        raise RuntimeError(msg)

    store = QdrantStore.from_settings()
    dim = await get_embedding_dim(settings.embeddings_model)

    if reset:
        await store.reset_collections(WDK_SEARCHES_V1, WDK_RECORD_TYPES_V1)

    await store.ensure_collection(name=WDK_RECORD_TYPES_V1, vector_size=dim)
    await store.ensure_collection(name=WDK_SEARCHES_V1, vector_size=dim)

    embedder = OpenAIEmbeddings(model=settings.embeddings_model)
    concurrency = min(40, max(1, int(os.cpu_count() or 1) * 10))
    logger.info(
        "WDK ingest starting",
        concurrency=concurrency,
        batch_size=batch_size,
        skip_existing=skip_existing,
    )

    router = get_site_router()
    all_sites = [s.id for s in router.list_sites()]
    selected = all_sites if not sites else [s for s in all_sites if s in set(sites)]

    # Skip portal sites during ingestion — their searches are a superset of
    # the individual component sites and cause many upstream 500 errors.
    # Individual sites (plasmodb, toxodb, etc.) cover all searches without
    # the portal's aggregation issues.
    portal_ids = {s.id for s in router.list_sites() if s.is_portal}
    if portal_ids:
        skipped = [s for s in selected if s in portal_ids]
        if skipped:
            logger.info(
                "Skipping portal sites (covered by individual sites)",
                skipped=skipped,
            )
        selected = [s for s in selected if s not in portal_ids]

    async with store.connect() as qdrant_client:
        for site_id in selected:
            logger.info("WDK ingest site", siteId=site_id)
            cfg = IngestSiteConfig(
                site_id=site_id,
                store=store,
                qdrant_client=qdrant_client,
                embedder=embedder,
                concurrency=concurrency,
                batch_size=max(8, int(batch_size)),
                skip_existing=bool(skip_existing) and (not bool(reset)),
            )
            try:
                await ingest_site(cfg)
            except (httpx.HTTPError, OSError, RuntimeError, AppError) as exc:
                logger.warning(
                    "WDK ingest site failed, continuing with remaining sites",
                    siteId=site_id,
                    error=str(exc),
                    errorType=type(exc).__name__,
                )


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
        sites=parse_sites(args.sites),
        reset=bool(args.reset),
        skip_existing=bool(args.skip_existing),
        batch_size=int(args.batch_size),
    )


def main(argv: list[str] | None = None) -> None:
    asyncio.run(_cli_async(argv))


if __name__ == "__main__":
    main()
