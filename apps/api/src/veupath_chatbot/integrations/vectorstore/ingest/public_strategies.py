import argparse
import asyncio
import json
import os
import time
import traceback
from pathlib import Path
from typing import cast

import httpx

from veupath_chatbot.integrations.embeddings.openai_embeddings import OpenAIEmbeddings
from veupath_chatbot.integrations.vectorstore.bootstrap import get_embedding_dim
from veupath_chatbot.integrations.vectorstore.collections import EXAMPLE_PLANS_V1
from veupath_chatbot.integrations.vectorstore.ingest.pipeline import (
    run_concurrent_pipeline,
)
from veupath_chatbot.integrations.vectorstore.ingest.public_fetch import (
    _delete_strategy,
    _duplicate_strategy,
    _fetch_public_strategy_summaries,
    _get_strategy_details,
)
from veupath_chatbot.integrations.vectorstore.ingest.public_index import _flush_batch
from veupath_chatbot.integrations.vectorstore.ingest.public_strategies_helpers import (
    embedding_text_for_example,
    full_strategy_payload,
    simplify_strategy_details,
)
from veupath_chatbot.integrations.vectorstore.ingest.public_transform import (
    _generate_name_and_description,
)
from veupath_chatbot.integrations.vectorstore.ingest.utils import (
    existing_point_ids,
    parse_sites,
)
from veupath_chatbot.integrations.vectorstore.qdrant_store import (
    QdrantStore,
    point_uuid,
    sha256_hex,
    stable_json_dumps,
)
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue

logger = get_logger(__name__)


def _now_ts() -> int:
    return int(time.time())


def _write_jsonl(path: Path, obj: JSONObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


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
            async with store.connect() as q:
                sigs = [str(s.get("signature") or "").strip() for s in candidates]
                sig_to_id = {sig: point_uuid(f"{site_id}:{sig}") for sig in sigs if sig}
                existing = await existing_point_ids(
                    qdrant_client=q,
                    collection=EXAMPLE_PLANS_V1,
                    ids=list(sig_to_id.values()),
                )

            if existing:
                before = len(candidates)
                candidates = [
                    s
                    for s, sig in zip(candidates, sigs, strict=True)
                    if sig and sig_to_id.get(sig) not in existing
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

        attempted = 0
        succeeded = 0
        failed = 0

        async def process_strategy(
            summary: JSONObject,
        ) -> tuple[JSONObject, str] | None:
            nonlocal attempted, succeeded
            signature = str(summary.get("signature") or "").strip()
            if not signature:
                return None

            attempted += 1
            tmp_id: int | None = None
            try:
                tmp_id = await _duplicate_strategy(client, signature)
                details = await _get_strategy_details(client, tmp_id)
            finally:
                if tmp_id is not None:
                    await _delete_strategy(client, tmp_id)

            compact = simplify_strategy_details(details)
            try:
                gen_name, gen_desc = await _generate_name_and_description(
                    strategy_compact=compact, model=llm_model
                )
            except Exception:
                gen_name = str(summary.get("name") or "Public strategy example").strip()
                gen_desc = str(summary.get("description") or "").strip() or gen_name

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
                "rootStepId": summary.get("rootStepId") or compact.get("rootStepId"),
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
            return payload, text

        def on_strategy_error(summary: JSONObject, exc: Exception) -> None:
            nonlocal failed
            failed += 1
            signature = str(summary.get("signature") or "").strip()
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

        async def flush_strategies(
            batch: list[tuple[JSONObject, str]],
        ) -> None:
            points: JSONArray = []
            texts: list[str] = []
            for payload, text in batch:
                pid = point_uuid(f"{site_id}:{payload['sourceSignature']}")
                points.append({"id": pid, "payload": payload})
                texts.append(text)
            await _flush_batch(
                store=store, embedder=embedder, points=points, texts=texts
            )

        await run_concurrent_pipeline(
            items=candidates,
            process_fn=process_strategy,
            flush_fn=flush_strategies,
            concurrency=concurrency,
            batch_size=10,
            on_error=on_strategy_error,
        )

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


async def ingest_public_strategies(
    *,
    sites: list[str] | None,
    reset: bool = False,
    llm_model: str = "gpt-4.1-nano",
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
    dim = await get_embedding_dim(settings.embeddings_model)

    if reset:
        await store.reset_collections(EXAMPLE_PLANS_V1)

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
        default="gpt-4.1-nano",
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
        sites=parse_sites(args.sites),
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
