import argparse
import asyncio
import json
import os
import time
import traceback
from dataclasses import dataclass
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


@dataclass
class IngestRunConfig:
    """Run-level options for :func:`ingest_public_strategies`."""

    sites: list[str] | None = None
    reset: bool = False
    llm_model: str = "gpt-4.1-nano"
    report_path: Path = Path("ingest_public_strategies_report.jsonl")
    max_strategies_per_site: int | None = None
    concurrency: int | None = None
    skip_existing: bool = True


@dataclass
class IngestSiteConfig:
    """Configuration bundle for :func:`ingest_site`."""

    site_id: str
    store: QdrantStore
    embedder: OpenAIEmbeddings
    llm_model: str
    report_path: Path
    max_strategies: int | None
    concurrency: int
    skip_existing: bool


def _filter_public_valid_candidates(summaries: list[JSONObject]) -> list[JSONObject]:
    """Return only public, valid, non-deleted strategy summaries."""
    candidates: list[JSONObject] = []
    for s in summaries:
        if not isinstance(s, dict):
            continue
        if (
            s.get("isPublic") is True
            and s.get("isValid") is True
            and s.get("isDeleted") is False
        ):
            candidates.append(s)
    return candidates


async def _skip_already_ingested(
    cfg: IngestSiteConfig,
    candidates: list[JSONObject],
) -> list[JSONObject]:
    """Remove candidates that already exist in Qdrant."""
    sigs = [str(s.get("signature") or "").strip() for s in candidates]
    sig_to_id = {sig: point_uuid(f"{cfg.site_id}:{sig}") for sig in sigs if sig}

    async with cfg.store.connect() as q:
        existing = await existing_point_ids(
            qdrant_client=q,
            collection=EXAMPLE_PLANS_V1,
            ids=list(sig_to_id.values()),
        )

    if not existing:
        return candidates

    before = len(candidates)
    filtered = [
        s
        for s, sig in zip(candidates, sigs, strict=True)
        if sig and sig_to_id.get(sig) not in existing
    ]
    skipped = before - len(filtered)
    if skipped:
        logger.info(
            "Example plans skipped (already ingested)",
            siteId=cfg.site_id,
            skipped=skipped,
        )
    return filtered


async def _process_single_strategy(
    cfg: IngestSiteConfig,
    client: httpx.AsyncClient,
    summary: JSONObject,
) -> tuple[JSONObject, str] | None:
    """Duplicate, fetch, simplify, and generate metadata for one strategy."""
    signature = str(summary.get("signature") or "").strip()
    if not signature:
        return None

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
            strategy_compact=compact, model=cfg.llm_model
        )
    except OSError, RuntimeError, ValueError, KeyError:
        gen_name = str(summary.get("name") or "Public strategy example").strip()
        gen_desc = str(summary.get("description") or "").strip() or gen_name

    payload: JSONObject = {
        "siteId": cfg.site_id,
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
    return payload, text


async def ingest_site(cfg: IngestSiteConfig) -> None:
    """Ingest public strategies for a single site."""
    router = get_site_router()
    site = router.get_site(cfg.site_id)

    async with httpx.AsyncClient(
        base_url=site.base_url.rstrip("/"),
        timeout=httpx.Timeout(90.0),
        follow_redirects=True,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    ) as client:
        try:
            summaries = await _fetch_public_strategy_summaries(client)
        except (httpx.HTTPError, OSError, RuntimeError) as exc:
            _write_jsonl(
                cfg.report_path,
                {
                    "ts": _now_ts(),
                    "siteId": cfg.site_id,
                    "level": "site",
                    "stage": "fetch_public_strategy_summaries",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            return

        candidates = _filter_public_valid_candidates(summaries)
        if cfg.max_strategies is not None:
            candidates = candidates[: max(0, int(cfg.max_strategies))]

        if cfg.skip_existing and candidates:
            candidates = await _skip_already_ingested(cfg, candidates)

        logger.info(
            "Example plans ingest candidates",
            siteId=cfg.site_id,
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
            attempted += 1
            result = await _process_single_strategy(cfg, client, summary)
            if result is not None:
                succeeded += 1
            return result

        def on_strategy_error(summary: JSONObject, exc: Exception) -> None:
            nonlocal failed
            failed += 1
            signature = str(summary.get("signature") or "").strip()
            _write_jsonl(
                cfg.report_path,
                {
                    "ts": _now_ts(),
                    "siteId": cfg.site_id,
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
                pid = point_uuid(f"{cfg.site_id}:{payload['sourceSignature']}")
                points.append({"id": pid, "payload": payload})
                texts.append(text)
            await _flush_batch(
                store=cfg.store, embedder=cfg.embedder, points=points, texts=texts
            )

        await run_concurrent_pipeline(
            items=candidates,
            process_fn=process_strategy,
            flush_fn=flush_strategies,
            concurrency=cfg.concurrency,
            batch_size=10,
            on_error=on_strategy_error,
        )

        _write_jsonl(
            cfg.report_path,
            {
                "ts": _now_ts(),
                "siteId": cfg.site_id,
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
                cfg.report_path,
                {
                    "ts": _now_ts(),
                    "siteId": cfg.site_id,
                    "level": "site",
                    "stage": "site_failed_all_strategies",
                    "candidates": len(candidates),
                    "attempted": attempted,
                    "failed": failed,
                },
            )


async def ingest_public_strategies(run_cfg: IngestRunConfig) -> None:
    """Ingest public strategies for all (or selected) VEuPathDB sites."""
    settings = get_settings()
    if not settings.openai_api_key:
        msg = "openai_api_key is required (embeddings + name/description generation)"
        raise RuntimeError(msg)

    store = QdrantStore.from_settings()
    dim = await get_embedding_dim(settings.embeddings_model)

    if run_cfg.reset:
        await store.reset_collections(EXAMPLE_PLANS_V1)

    await store.ensure_collection(name=EXAMPLE_PLANS_V1, vector_size=dim)
    embedder = OpenAIEmbeddings(model=settings.embeddings_model)

    router = get_site_router()
    all_sites = [s.id for s in router.list_sites()]
    sites = run_cfg.sites
    selected = all_sites if not sites else [s for s in all_sites if s in set(sites)]

    conc = (
        run_cfg.concurrency
        if run_cfg.concurrency is not None
        else max(1, int(os.cpu_count() or 1))
    )

    _write_jsonl(
        run_cfg.report_path,
        {
            "ts": _now_ts(),
            "level": "run",
            "stage": "start",
            "sites": cast("JSONValue", selected),
            "llmModel": str(run_cfg.llm_model),
            "skipExisting": bool(run_cfg.skip_existing),
            "maxStrategiesPerSite": run_cfg.max_strategies_per_site,
            "concurrency": conc,
        },
    )

    for site_id in selected:
        logger.info("Example plans ingest site", siteId=site_id)
        cfg = IngestSiteConfig(
            site_id=site_id,
            store=store,
            embedder=embedder,
            llm_model=str(run_cfg.llm_model),
            report_path=run_cfg.report_path,
            max_strategies=run_cfg.max_strategies_per_site,
            concurrency=conc,
            skip_existing=bool(run_cfg.skip_existing) and (not bool(run_cfg.reset)),
        )
        try:
            await ingest_site(cfg)
        except (httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
            _write_jsonl(
                run_cfg.report_path,
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

    _write_jsonl(run_cfg.report_path, {"ts": _now_ts(), "level": "run", "stage": "end"})


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
        IngestRunConfig(
            sites=parse_sites(args.sites),
            reset=bool(args.reset),
            skip_existing=bool(args.skip_existing),
            llm_model=str(args.llm_model),
            report_path=Path(str(args.report_path)),
            max_strategies_per_site=args.max_strategies_per_site,
            concurrency=args.concurrency,
        )
    )


def main(argv: list[str] | None = None) -> None:
    asyncio.run(_cli_async(argv))


if __name__ == "__main__":
    main()
