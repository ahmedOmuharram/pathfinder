from __future__ import annotations

import argparse
import asyncio
import os
import time
from typing import Any, cast

from qdrant_client import AsyncQdrantClient

from veupath_chatbot.domain.parameters.specs import extract_param_specs
from veupath_chatbot.domain.parameters.vocab_utils import flatten_vocab
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.embeddings.openai_embeddings import (
    OpenAIEmbeddings,
    embed_one,
)
from veupath_chatbot.services.vectorstore.collections import (
    WDK_RECORD_TYPES_V1,
    WDK_SEARCHES_V1,
)
from veupath_chatbot.services.vectorstore.ingest.utils import existing_point_ids
from veupath_chatbot.services.vectorstore.qdrant_store import (
    QdrantStore,
    point_uuid,
    sha256_hex,
    stable_json_dumps,
)

logger = get_logger(__name__)


def _unwrap_search_data(details: JSONObject | None) -> JSONObject:
    if not isinstance(details, dict):
        return {}
    search_data = details.get("searchData")
    if isinstance(search_data, dict):
        return search_data
    return details


def _coerce_str(value: object | None) -> str:
    return str(value) if value is not None else ""


def _preview_vocab(vocab: JSONValue, *, limit: int = 50) -> tuple[list[str], bool]:
    if not vocab:
        return [], False
    values: list[str] = []
    seen: set[str] = set()
    truncated = False
    vocab_input: JSONObject | JSONArray
    if isinstance(vocab, (dict, list)):
        vocab_input = vocab
    else:
        return [], False
    for entry in flatten_vocab(vocab_input, prefer_term=False):
        candidate = entry.get("display") or entry.get("value")
        if not candidate:
            continue
        s = str(candidate)
        if s in seen:
            continue
        seen.add(s)
        values.append(s)
        if len(values) >= limit:
            truncated = True
            break
    return values, truncated


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

    raw_record_types = await client.get_record_types(expanded=True)
    if isinstance(raw_record_types, dict):
        raw_record_types = (
            raw_record_types.get("recordTypes")
            or raw_record_types.get("records")
            or raw_record_types.get("result")
            or []
        )

    record_type_docs: JSONArray = []
    searches_to_fetch: list[tuple[str, JSONObject]] = []

    # Record types + basic search lists.
    for rt in raw_record_types or []:
        searches: JSONArray = []
        if isinstance(rt, str):
            rt_name = rt
            rt_display = rt
            rt_desc = ""
        elif isinstance(rt, dict):
            rt_name = str(rt.get("urlSegment") or rt.get("name") or "").strip()
            rt_display = str(rt.get("displayName") or rt_name)
            rt_desc = str(rt.get("description") or "")
            searches_raw = rt.get("searches")
            searches = searches_raw if isinstance(searches_raw, list) else []
        else:
            continue

        if not rt_name:
            continue

        record_type_docs.append(
            {
                "id": point_uuid(f"{site_id}:{rt_name}"),
                "text": f"{rt_display}\n{rt_name}\n{rt_desc}".strip(),
                "payload": {
                    "siteId": site_id,
                    "recordType": rt_name,
                    "displayName": rt_display,
                    "description": rt_desc,
                    "displayNamePlural": rt.get("displayNamePlural")
                    if isinstance(rt, dict)
                    else None,
                    "shortDisplayName": rt.get("shortDisplayName")
                    if isinstance(rt, dict)
                    else None,
                    "shortDisplayNamePlural": rt.get("shortDisplayNamePlural")
                    if isinstance(rt, dict)
                    else None,
                    "fullName": rt.get("fullName") if isinstance(rt, dict) else None,
                    "urlSegment": rt.get("urlSegment")
                    if isinstance(rt, dict)
                    else rt_name,
                    "name": rt.get("name") if isinstance(rt, dict) else rt_name,
                    "iconName": rt.get("iconName") if isinstance(rt, dict) else None,
                    "recordIdAttributeName": rt.get("recordIdAttributeName")
                    if isinstance(rt, dict)
                    else None,
                    "primaryKeyColumnRefs": rt.get("primaryKeyColumnRefs")
                    if isinstance(rt, dict)
                    else None,
                    "useBasket": rt.get("useBasket") if isinstance(rt, dict) else None,
                    "formats": rt.get("formats") if isinstance(rt, dict) else None,
                    "attributes": rt.get("attributes")
                    if isinstance(rt, dict)
                    else None,
                    "tables": rt.get("tables") if isinstance(rt, dict) else None,
                    "source": "wdk",
                },
            }
        )

        # If expanded record-types payload did not include searches, we will load later.
        if isinstance(searches, list) and searches:
            for s in searches:
                if isinstance(s, dict):
                    searches_to_fetch.append((rt_name, s))
        else:
            try:
                searches_raw = await client.get_searches(rt_name)
                searches = searches_raw if isinstance(searches_raw, list) else []
            except Exception:
                searches = []
            for s in searches or []:
                if isinstance(s, dict):
                    searches_to_fetch.append((rt_name, s))

    if skip_existing:
        # Filter record types already present.
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

        # Filter searches already present.
        enriched: list[tuple[str, JSONObject, str]] = []
        for rt_name, s in searches_to_fetch:
            if not isinstance(s, dict):
                continue
            if s.get("isInternal", False):
                continue
            search_name = str(s.get("urlSegment") or s.get("name") or "").strip()
            if not search_name:
                continue
            enriched.append(
                (rt_name, s, point_uuid(f"{site_id}:{rt_name}:{search_name}"))
            )

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

        # Keep original shape for workers.
        searches_to_fetch = [(rt_name, s) for rt_name, s, _ in enriched]

    # Upsert record types.
    if record_type_docs:
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

    # Fetch search details and upsert searches (concurrently).
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
                if not isinstance(s, dict):
                    await docs.put(None)
                    continue
                if s.get("isInternal", False):
                    await docs.put(None)
                    continue
                search_name = str(s.get("urlSegment") or s.get("name") or "").strip()
                if not search_name:
                    await docs.put(None)
                    continue

                details_error: str | None = None
                summary_unwrapped = _unwrap_search_data(
                    s if isinstance(s, dict) else {}
                )
                details_unwrapped: JSONObject = {}
                try:
                    has_param_defs = any(
                        k in summary_unwrapped
                        for k in ("parameters", "paramSpecs", "parameterSpecs")
                    ) or (
                        isinstance(summary_unwrapped.get("searchData"), dict)
                        and isinstance(summary_unwrapped["searchData"], dict)
                        and any(
                            k in summary_unwrapped["searchData"]
                            for k in ("parameters", "paramSpecs", "parameterSpecs")
                        )
                    )
                    param_names = summary_unwrapped.get("paramNames")
                    if has_param_defs or (
                        isinstance(param_names, list) and len(param_names) == 0
                    ):
                        details_unwrapped = summary_unwrapped
                    else:
                        details = await client.get_search_details(
                            rt_name, search_name, expand_params=True
                        )
                        details_unwrapped = _unwrap_search_data(
                            details if isinstance(details, dict) else {}
                        )
                except Exception as exc:
                    failed_details += 1
                    details_error = str(exc)
                    details_unwrapped = {}

                raw_specs = (
                    extract_param_specs(details_unwrapped) if details_unwrapped else []
                )
                canonical_params: JSONArray = []
                for spec in raw_specs:
                    if not isinstance(spec, dict):
                        continue
                    name = spec.get("name") or spec.get("paramName") or spec.get("id")
                    if not name:
                        continue
                    vocab = spec.get("vocabulary")
                    vocab_preview, vocab_truncated = _preview_vocab(vocab, limit=50)
                    canonical_params.append(
                        {
                            "name": str(name),
                            "displayName": spec.get("displayName") or str(name),
                            "type": spec.get("type") or "string",
                            "help": spec.get("help") or "",
                            "isRequired": bool(spec.get("isRequired", False))
                            if "isRequired" in spec
                            else (not bool(spec.get("allowEmptyValue", False))),
                            "allowEmptyValue": bool(spec.get("allowEmptyValue", True))
                            if "allowEmptyValue" in spec
                            else None,
                            "defaultValue": spec.get("defaultValue")
                            if spec.get("defaultValue") is not None
                            else spec.get("initialDisplayValue"),
                            "vocabulary": vocab,
                            "vocabularyPreview": cast(Any, vocab_preview),
                            "vocabularyTruncated": vocab_truncated,
                        }
                    )

                display_name = _coerce_str(
                    details_unwrapped.get("displayName")
                    or s.get("displayName")
                    or s.get("shortDisplayName")
                    or search_name
                )
                short = _coerce_str(
                    details_unwrapped.get("shortDisplayName")
                    or s.get("shortDisplayName")
                    or ""
                )
                description = _coerce_str(
                    details_unwrapped.get("description") or s.get("description") or ""
                )
                summary = _coerce_str(details_unwrapped.get("summary") or "")
                help_text = _coerce_str(details_unwrapped.get("help") or "")

                payload: JSONObject = {
                    "siteId": site_id,
                    "recordType": rt_name,
                    "searchName": search_name,
                    "displayName": display_name,
                    "shortDisplayName": short,
                    "description": description,
                    "summary": summary,
                    "help": help_text,
                    "isInternal": bool(s.get("isInternal", False)),
                    "paramSpecs": canonical_params,
                    "fullName": details_unwrapped.get("fullName")
                    or summary_unwrapped.get("fullName"),
                    "urlSegment": details_unwrapped.get("urlSegment")
                    or summary_unwrapped.get("urlSegment")
                    or search_name,
                    "outputRecordClassName": details_unwrapped.get(
                        "outputRecordClassName"
                    )
                    or rt_name,
                    "paramNames": details_unwrapped.get("paramNames")
                    or summary_unwrapped.get("paramNames"),
                    "groups": details_unwrapped.get("groups")
                    or summary_unwrapped.get("groups"),
                    "filters": details_unwrapped.get("filters")
                    or summary_unwrapped.get("filters"),
                    "defaultAttributes": details_unwrapped.get("defaultAttributes")
                    or summary_unwrapped.get("defaultAttributes"),
                    "defaultSorting": details_unwrapped.get("defaultSorting")
                    or summary_unwrapped.get("defaultSorting"),
                    "dynamicAttributes": details_unwrapped.get("dynamicAttributes")
                    or summary_unwrapped.get("dynamicAttributes"),
                    "defaultSummaryView": details_unwrapped.get("defaultSummaryView")
                    or summary_unwrapped.get("defaultSummaryView"),
                    "noSummaryOnSingleRecord": details_unwrapped.get(
                        "noSummaryOnSingleRecord"
                    )
                    or summary_unwrapped.get("noSummaryOnSingleRecord"),
                    "summaryViewPlugins": details_unwrapped.get("summaryViewPlugins")
                    or summary_unwrapped.get("summaryViewPlugins"),
                    "allowedPrimaryInputRecordClassNames": details_unwrapped.get(
                        "allowedPrimaryInputRecordClassNames"
                    ),
                    "allowedSecondaryInputRecordClassNames": details_unwrapped.get(
                        "allowedSecondaryInputRecordClassNames"
                    ),
                    "isAnalyzable": details_unwrapped.get("isAnalyzable")
                    or summary_unwrapped.get("isAnalyzable"),
                    "isCacheable": details_unwrapped.get("isCacheable")
                    or summary_unwrapped.get("isCacheable"),
                    "isBeta": details_unwrapped.get("isBeta"),
                    "queryName": details_unwrapped.get("queryName")
                    or summary_unwrapped.get("queryName"),
                    "newBuild": details_unwrapped.get("newBuild"),
                    "reviseBuild": details_unwrapped.get("reviseBuild"),
                    "searchVisibleHelp": details_unwrapped.get("searchVisibleHelp"),
                    "sourceUrl": f"{client.base_url}/record-types/{rt_name}/searches/{search_name}",
                    "ingestedAt": int(time.time()),
                }
                if details_error:
                    payload["detailsError"] = details_error
                payload["sourceHash"] = sha256_hex(stable_json_dumps(payload))

                text = "\n".join(
                    [
                        display_name,
                        search_name,
                        rt_name,
                        summary,
                        description,
                        " ".join(
                            (
                                f"{p.get('name', '')} {p.get('displayName', '')} "
                                f"{p.get('type', '')} {p.get('help', '')}"
                            )
                            for p in canonical_params
                            if isinstance(p, dict)
                        ),
                    ]
                ).strip()

                await docs.put(
                    {
                        "id": point_uuid(f"{site_id}:{rt_name}:{search_name}"),
                        "text": text,
                        "payload": payload,
                    }
                )
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
                buffered.clear()

        if buffered:
            texts_final: list[str] = []
            valid_docs_final: list[JSONObject] = []
            for d in buffered:
                if isinstance(d, dict):
                    text_value = d.get("text")
                    if isinstance(text_value, str):
                        texts_final.append(text_value)
                        valid_docs_final.append(d)
            vectors = await embedder.embed_texts(texts_final)
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
                    for d, v in zip(valid_docs_final, vectors, strict=True)
                ],
            )

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
        from qdrant_client import AsyncQdrantClient

        client = AsyncQdrantClient(
            url=store.url,
            api_key=store.api_key,
            timeout=int(store.timeout_seconds)
            if store.timeout_seconds is not None
            else None,
        )
        for name in (WDK_SEARCHES_V1, WDK_RECORD_TYPES_V1):
            if await client.collection_exists(collection_name=name):
                await client.delete_collection(collection_name=name)

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

    from qdrant_client import AsyncQdrantClient

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
