from __future__ import annotations

import asyncio
from pathlib import Path

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.vectorstore.ingest.public_strategies import (
    ingest_public_strategies,
)
from veupath_chatbot.services.vectorstore.ingest.wdk_catalog import ingest_wdk_catalog

logger = get_logger(__name__)

_startup_task: asyncio.Task[None] | None = None
_startup_lock = asyncio.Lock()


async def start_rag_startup_ingestion_background() -> None:
    """Fire-and-forget incremental ingestion at API startup.

    - Runs only when `rag_enabled=true` and `OPENAI_API_KEY` is set.
    - Never blocks API startup.
    - Only runs once per process.
    """
    global _startup_task

    settings = get_settings()
    if not settings.rag_enabled:
        return
    if not settings.openai_api_key:
        logger.warning(
            "RAG enabled but OPENAI_API_KEY not set; skipping startup ingestion"
        )
        return

    async with _startup_lock:
        if _startup_task is not None and not _startup_task.done():
            return

        async def _run() -> None:
            max_per_site = settings.rag_startup_max_strategies_per_site
            conc = settings.rag_startup_public_strategies_concurrency
            llm_model = (
                settings.rag_startup_public_strategies_llm_model or "gpt-4o-mini"
            ).strip()
            report_path = Path(
                settings.rag_startup_public_strategies_report_path
                or "/tmp/ingest_public_strategies_report.jsonl"
            )

            logger.info(
                "RAG startup ingestion begin",
                maxStrategiesPerSite=max_per_site,
                publicStrategiesConcurrency=conc,
                publicStrategiesLlmModel=llm_model,
            )
            try:
                # 1) WDK catalog (record types + searches)
                await ingest_wdk_catalog(sites=None, reset=False, skip_existing=True)

                # 2) Example plans from public strategies
                await ingest_public_strategies(
                    sites=None,
                    reset=False,
                    skip_existing=True,
                    llm_model=llm_model,
                    report_path=report_path,
                    max_strategies_per_site=max_per_site,
                    concurrency=conc,
                )
            except Exception as exc:
                logger.error(
                    "RAG startup ingestion failed",
                    error=str(exc),
                    errorType=type(exc).__name__,
                )
                return

            logger.info("RAG startup ingestion complete")

        _startup_task = asyncio.create_task(_run())
