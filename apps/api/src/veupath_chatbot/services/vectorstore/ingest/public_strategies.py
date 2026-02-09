from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import traceback
from pathlib import Path
from typing import cast

import httpx

from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.embeddings.openai_embeddings import (
    OpenAIEmbeddings,
    embed_one,
)
from veupath_chatbot.services.vectorstore.collections import EXAMPLE_PLANS_V1
from veupath_chatbot.services.vectorstore.ingest.public_strategies_helpers import (
    EMBED_TEXT_MAX_CHARS,
    backoff_delay_seconds,
    embedding_text_for_example,
    full_strategy_payload,
    simplify_strategy_details,
    truncate,
)
from veupath_chatbot.services.vectorstore.ingest.utils import existing_point_ids
from veupath_chatbot.services.vectorstore.qdrant_store import (
    QdrantStore,
    point_uuid,
    sha256_hex,
    stable_json_dumps,
)

logger = get_logger(__name__)


def _now_ts() -> int:
    return int(time.time())


def _write_jsonl(path: Path, obj: JSONObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


async def _sleep_backoff(attempt: int) -> None:
    await asyncio.sleep(backoff_delay_seconds(attempt))


async def _generate_name_and_description(
    *, strategy_compact: JSONObject, model: str
) -> tuple[str, str]:
    settings = get_settings()
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key or None)
    compact_json = json.dumps(strategy_compact, ensure_ascii=False)
    prompt = f"""You are generating metadata for a public strategy example.

Return STRICT JSON with keys:
- name: short, human-friendly title (max 80 chars)
- description: 3-8 sentences. Must be descriptive but MUST NOT be a step-by-step recipe.
  It MUST explicitly include the requirements/criteria represented in the strategy, including:
  - all searches used (searchName)
  - all parameter constraints used for each step (parameters key/value pairs)
  - boolean operators (INTERSECT/UNION/MINUS/RMINUS/COLOCATE) when present

Do not write "Step 1", "Step 2" or numbered steps.
Do not include markdown.

Strategy (compact JSON):
{compact_json}
"""

    resp = await client.chat.completions.create(
        model=model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": prompt},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("Empty LLM response")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start : end + 1])
        else:
            raise
    name = str(data.get("name") or "").strip()
    desc = str(data.get("description") or "").strip()
    if not name or not desc:
        raise RuntimeError("LLM returned empty name/description")
    return name, desc


async def _fetch_public_strategy_summaries(
    client: httpx.AsyncClient,
) -> JSONArray:
    resp = await client.get("/strategy-lists/public")
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


async def _duplicate_strategy(client: httpx.AsyncClient, signature: str) -> int:
    last_exc: Exception | None = None
    for attempt in range(1, 6):
        try:
            resp = await client.post(
                "/users/current/strategies",
                json={"sourceStrategySignature": signature},
                timeout=httpx.Timeout(90.0),
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict) or "id" not in data:
                raise RuntimeError("Unexpected duplicateStrategy response")
            return int(data["id"])
        except (
            httpx.ReadTimeout,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ) as exc:
            last_exc = exc
            await _sleep_backoff(attempt)
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            status = exc.response.status_code
            if status in (429, 500, 502, 503, 504):
                await _sleep_backoff(attempt)
            else:
                raise
    raise RuntimeError(f"duplicate_strategy failed after retries: {last_exc!r}")


async def _get_strategy_details(
    client: httpx.AsyncClient, strategy_id: int
) -> JSONObject:
    last_exc: Exception | None = None
    for attempt in range(1, 6):
        try:
            resp = await client.get(
                f"/users/current/strategies/{strategy_id}",
                timeout=httpx.Timeout(180.0),
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise RuntimeError("Unexpected strategy details response")
            return data
        except (
            httpx.ReadTimeout,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ) as exc:
            last_exc = exc
            await _sleep_backoff(attempt)
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            status = exc.response.status_code
            if status in (429, 500, 502, 503, 504):
                await _sleep_backoff(attempt)
            else:
                raise
    raise RuntimeError(f"get_strategy_details failed after retries: {last_exc!r}")


async def _delete_strategy(client: httpx.AsyncClient, strategy_id: int) -> None:
    resp = await client.delete(f"/users/current/strategies/{strategy_id}")
    if resp.status_code >= 400:
        return


async def ingest_site(
    *,
    site_id: str,
    store: QdrantStore,
    embedder: OpenAIEmbeddings,
    llm_model: str,
    report_path: Path,
    max_strategies: int | None,
    concurrency: int,
    skip_existing: bool,
) -> None:
    router = get_site_router()
    site = router.get_site(site_id)

    async with httpx.AsyncClient(
        base_url=site.base_url.rstrip("/"),
        timeout=httpx.Timeout(90.0),
        follow_redirects=True,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    ) as client:
        try:
            summaries = await _fetch_public_strategy_summaries(client)
        except Exception as exc:
            _write_jsonl(
                report_path,
                {
                    "ts": _now_ts(),
                    "siteId": site_id,
                    "level": "site",
                    "stage": "fetch_public_strategy_summaries",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            return

        candidates: list[JSONObject] = []
        for s in summaries:
            if not isinstance(s, dict):
                continue
            is_public_raw = s.get("isPublic")
            is_valid_raw = s.get("isValid")
            is_deleted_raw = s.get("isDeleted")
            if (
                is_public_raw is True
                and is_valid_raw is True
                and is_deleted_raw is False
            ):
                candidates.append(s)
        if max_strategies is not None:
            candidates = candidates[: max(0, int(max_strategies))]

        if skip_existing and candidates:
            # Filter candidates whose point already exists in Qdrant.
            from qdrant_client import AsyncQdrantClient

            timeout_int: int | None = (
                int(store.timeout_seconds)
                if store.timeout_seconds is not None
                else None
            )
            q = AsyncQdrantClient(
                url=store.url,
                api_key=store.api_key,
                timeout=timeout_int,
            )
            try:
                sigs = [str(s.get("signature") or "").strip() for s in candidates]
                ids = [point_uuid(f"{site_id}:{sig}") for sig in sigs if sig]
                existing = await existing_point_ids(
                    qdrant_client=q, collection=EXAMPLE_PLANS_V1, ids=ids
                )
            finally:
                await q.close()

            if existing:
                before = len(candidates)
                candidates = [
                    s
                    for s in candidates
                    if str(s.get("signature") or "").strip()
                    and point_uuid(f"{site_id}:{str(s.get('signature') or '').strip()}")
                    not in existing
                ]
                skipped = before - len(candidates)
                if skipped:
                    logger.info(
                        "Example plans skipped (already ingested)",
                        siteId=site_id,
                        skipped=skipped,
                    )

        logger.info(
            "Example plans ingest candidates",
            siteId=site_id,
            candidates=len(candidates),
            total_listed=len(summaries),
        )

        sem = asyncio.Semaphore(max(1, int(concurrency)))
        jobs: asyncio.Queue[JSONObject | None] = asyncio.Queue()
        docs: asyncio.Queue[tuple[JSONObject, str] | None] = asyncio.Queue()

        attempted = 0
        succeeded = 0
        failed = 0

        async def worker() -> None:
            nonlocal attempted, succeeded, failed
            while True:
                item = await jobs.get()
                if item is None:
                    jobs.task_done()
                    break
                summary = item
                signature = str(summary.get("signature") or "").strip()
                if not signature:
                    jobs.task_done()
                    continue
                async with sem:
                    attempted += 1
                    tmp_id: int | None = None
                    try:
                        tmp_id = await _duplicate_strategy(client, signature)
                        details = await _get_strategy_details(client, tmp_id)
                    except Exception as exc:
                        failed += 1
                        _write_jsonl(
                            report_path,
                            {
                                "ts": _now_ts(),
                                "siteId": site_id,
                                "level": "strategy",
                                "stage": "duplicate_or_fetch_details",
                                "sourceSignature": signature,
                                "sourceStrategyId": summary.get("strategyId"),
                                "error": repr(exc),
                                "traceback": traceback.format_exc(),
                            },
                        )
                        if tmp_id is not None:
                            await _delete_strategy(client, tmp_id)
                        jobs.task_done()
                        continue
                    finally:
                        if tmp_id is not None:
                            await _delete_strategy(client, tmp_id)

                    compact = simplify_strategy_details(details)
                    try:
                        gen_name, gen_desc = await _generate_name_and_description(
                            strategy_compact=compact, model=llm_model
                        )
                    except Exception:
                        gen_name = str(
                            summary.get("name") or "Public strategy example"
                        ).strip()
                        gen_desc = (
                            str(summary.get("description") or "").strip() or gen_name
                        )

                    payload: JSONObject = {
                        "siteId": site_id,
                        "sourceSignature": signature,
                        "sourceStrategyId": summary.get("strategyId"),
                        "sourceName": summary.get("name"),
                        "sourceDescription": summary.get("description"),
                        "generatedName": gen_name,
                        "generatedDescription": gen_desc,
                        "recordClassName": summary.get("recordClassName")
                        or compact.get("recordClassName"),
                        "rootStepId": summary.get("rootStepId")
                        or compact.get("rootStepId"),
                        "strategyCompact": compact,
                        "strategyFull": full_strategy_payload(details),
                        "ingestedAt": int(time.time()),
                    }
                    payload["sourceHash"] = sha256_hex(stable_json_dumps(payload))

                    text = embedding_text_for_example(
                        name=gen_name,
                        description=gen_desc,
                        compact=compact,
                    )
                    succeeded += 1
                    await docs.put((payload, text))
                jobs.task_done()

        async def consumer() -> None:
            points: JSONArray = []
            texts: list[str] = []
            while True:
                item = await docs.get()
                if item is None:
                    docs.task_done()
                    break
                payload, text = item
                docs.task_done()
                point_id = point_uuid(f"{site_id}:{payload['sourceSignature']}")
                points.append({"id": point_id, "payload": payload})
                texts.append(text)
                if len(points) >= 10:
                    await _flush_batch(
                        store=store, embedder=embedder, points=points, texts=texts
                    )

            if points:
                await _flush_batch(
                    store=store, embedder=embedder, points=points, texts=texts
                )

        workers = [
            asyncio.create_task(worker()) for _ in range(max(1, int(concurrency)))
        ]
        consumer_task = asyncio.create_task(consumer())

        for s in candidates:
            await jobs.put(s)
        for _ in workers:
            await jobs.put(None)

        await jobs.join()
        await docs.put(None)
        await consumer_task
        for w in workers:
            await w

        _write_jsonl(
            report_path,
            {
                "ts": _now_ts(),
                "siteId": site_id,
                "level": "site",
                "stage": "site_complete",
                "candidates": len(candidates),
                "attempted": attempted,
                "succeeded": succeeded,
                "failed": failed,
            },
        )
        if len(candidates) > 0 and succeeded == 0:
            _write_jsonl(
                report_path,
                {
                    "ts": _now_ts(),
                    "siteId": site_id,
                    "level": "site",
                    "stage": "site_failed_all_strategies",
                    "candidates": len(candidates),
                    "attempted": attempted,
                    "failed": failed,
                },
            )


async def _flush_batch(
    *,
    store: QdrantStore,
    embedder: OpenAIEmbeddings,
    points: JSONArray,
    texts: list[str],
) -> None:
    if not points:
        return
    safe_texts = [truncate(t, max_chars=EMBED_TEXT_MAX_CHARS) for t in texts]
    try:
        vectors = await embedder.embed_texts(safe_texts)
    except Exception:
        vectors = []
        for t in safe_texts:
            tt = truncate(t, max_chars=10_000)
            vectors.append((await embedder.embed_texts([tt]))[0])
    upsert_points: JSONArray = []
    for p, v in zip(points, vectors, strict=True):
        if not isinstance(p, dict):
            continue
        id_raw = p.get("id")
        payload_raw = p.get("payload")
        point_dict: JSONObject = {
            "id": id_raw,
            "vector": cast(JSONValue, v),
            "payload": payload_raw,
        }
        upsert_points.append(cast(JSONValue, point_dict))
    await store.upsert(
        collection=EXAMPLE_PLANS_V1,
        points=upsert_points,
    )
    points.clear()
    texts.clear()


async def ingest_public_strategies(
    *,
    sites: list[str] | None,
    reset: bool = False,
    llm_model: str = "gpt-4o-mini",
    report_path: Path = Path("ingest_public_strategies_report.jsonl"),
    max_strategies_per_site: int | None = None,
    concurrency: int | None = None,
    skip_existing: bool = True,
) -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "openai_api_key is required (embeddings + name/description generation)"
        )

    store = QdrantStore.from_settings()
    dim = len(await embed_one(text="example-plans", model=settings.embeddings_model))

    if reset:
        from qdrant_client import AsyncQdrantClient

        timeout_int: int | None = (
            int(store.timeout_seconds) if store.timeout_seconds is not None else None
        )
        client = AsyncQdrantClient(
            url=store.url,
            api_key=store.api_key,
            timeout=timeout_int,
        )
        if await client.collection_exists(collection_name=EXAMPLE_PLANS_V1):
            await client.delete_collection(collection_name=EXAMPLE_PLANS_V1)

    await store.ensure_collection(name=EXAMPLE_PLANS_V1, vector_size=dim)
    embedder = OpenAIEmbeddings(model=settings.embeddings_model)

    router = get_site_router()
    all_sites = [s.id for s in router.list_sites()]
    selected = all_sites if not sites else [s for s in all_sites if s in set(sites)]

    conc = concurrency if concurrency is not None else max(1, int(os.cpu_count() or 1))

    _write_jsonl(
        report_path,
        {
            "ts": _now_ts(),
            "level": "run",
            "stage": "start",
            "sites": cast(JSONValue, selected),
            "llmModel": str(llm_model),
            "skipExisting": bool(skip_existing),
            "maxStrategiesPerSite": max_strategies_per_site,
            "concurrency": conc,
        },
    )

    for site_id in selected:
        logger.info("Example plans ingest site", siteId=site_id)
        try:
            await ingest_site(
                site_id=site_id,
                store=store,
                embedder=embedder,
                llm_model=str(llm_model),
                report_path=report_path,
                max_strategies=max_strategies_per_site,
                concurrency=conc,
                skip_existing=bool(skip_existing) and (not bool(reset)),
            )
        except Exception as exc:
            _write_jsonl(
                report_path,
                {
                    "ts": _now_ts(),
                    "siteId": site_id,
                    "level": "site",
                    "stage": "unhandled_exception",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            continue

    _write_jsonl(report_path, {"ts": _now_ts(), "level": "run", "stage": "end"})


def _parse_sites(value: str) -> list[str] | None:
    v = (value or "").strip()
    if not v or v == "all":
        return None
    return [s.strip() for s in v.split(",") if s.strip()]


async def _cli_async(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sites", default="all")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip strategies already present in Qdrant (default: true).",
    )
    parser.add_argument(
        "--llm-model",
        default="gpt-4o-mini",
        help="Model for generating name/description (uses same OpenAI API key).",
    )
    parser.add_argument(
        "--report-path",
        default="ingest_public_strategies_report.jsonl",
        help="Write failures/progress as JSONL (append-only).",
    )
    parser.add_argument(
        "--max-strategies-per-site",
        type=int,
        default=None,
        help="Optional cap per site (useful for debugging/cost control).",
    )
    parser.add_argument("--concurrency", type=int, default=None)
    args = parser.parse_args(argv)

    await ingest_public_strategies(
        sites=_parse_sites(args.sites),
        reset=bool(args.reset),
        skip_existing=bool(args.skip_existing),
        llm_model=str(args.llm_model),
        report_path=Path(str(args.report_path)),
        max_strategies_per_site=args.max_strategies_per_site,
        concurrency=args.concurrency,
    )


def main(argv: list[str] | None = None) -> None:
    asyncio.run(_cli_async(argv))


if __name__ == "__main__":
    main()
