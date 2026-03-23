"""Seed strategy runner.

Creates real WDK strategies (visible in the sidebar) and curated control sets
(available in the Experiments tab) across multiple VEuPathDB sites.

Seeds are processed concurrently across sites using ``asyncio.TaskGroup``,
with a semaphore to cap the number of parallel WDK requests.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.persistence.repositories.control_set import ControlSetCreate
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.materialization import (
    _materialize_step_tree,
)
from veupath_chatbot.services.experiment.seed.seeds import (
    get_all_seeds,
    get_seeds_for_site,
)
from veupath_chatbot.services.strategies.wdk_sync import sync_to_projection

logger = get_logger(__name__)

_MAX_CONCURRENT_SEEDS = 10


@dataclass
class _SeedRunContext:
    """Shared execution infrastructure for seed processing.

    Groups the four per-run resources that ``_process_single_seed`` needs
    to keep its parameter count within the 6-argument limit.
    """

    total: int
    semaphore: asyncio.Semaphore
    queue: asyncio.Queue[JSONObject | None]
    stream_repo: Any
    control_set_repo: Any
    user_id: UUID


async def _process_single_seed(
    i: int,
    seed: Any,
    ctx: _SeedRunContext,
) -> tuple[bool, bool]:
    """Process a single seed. Returns (strategy_ok, control_set_ok)."""
    idx = i + 1
    async with ctx.semaphore:
        await ctx.queue.put(
            {
                "type": "seed_progress",
                "data": {
                    "phase": "running",
                    "current": idx,
                    "total": ctx.total,
                    "name": seed.name,
                    "message": f"[{idx}/{ctx.total}] Creating strategy: {seed.name}",
                },
            }
        )

        t0 = time.monotonic()
        try:
            api = get_strategy_api(seed.site_id)

            tree_node = PlanStepNode.model_validate(seed.step_tree)
            root_tree = await _materialize_step_tree(
                api, tree_node, seed.record_type, site_id=seed.site_id
            )

            created = await api.create_strategy(
                step_tree=root_tree,
                name=seed.name,
                description=seed.description,
                is_saved=True,
            )
            wdk_strategy_id = created.id

            await sync_to_projection(
                wdk_id=wdk_strategy_id,
                site_id=seed.site_id,
                api=api,
                stream_repo=ctx.stream_repo,
                user_id=ctx.user_id,
            )

            elapsed_strategy = time.monotonic() - t0
            await ctx.queue.put(
                {
                    "type": "seed_strategy_complete",
                    "data": {
                        "current": idx,
                        "total": ctx.total,
                        "name": seed.name,
                        "wdkStrategyId": wdk_strategy_id,
                        "elapsed": round(elapsed_strategy, 1),
                        "message": f"[{idx}/{ctx.total}] Strategy created: {seed.name}",
                    },
                }
            )

            cs = seed.control_set
            await ctx.control_set_repo.create(
                ControlSetCreate(
                    name=cs.name,
                    site_id=seed.site_id,
                    record_type=seed.record_type,
                    positive_ids=cs.positive_ids,
                    negative_ids=cs.negative_ids,
                    source="curation",
                    tags=cs.tags or [],
                    provenance_notes=cs.provenance_notes,
                    is_public=True,
                    user_id=ctx.user_id,
                )
            )

        except Exception as exc:
            elapsed = time.monotonic() - t0
            logger.exception("Seed failed", name=seed.name, error=str(exc))
            await ctx.queue.put(
                {
                    "type": "seed_item_error",
                    "data": {
                        "current": idx,
                        "total": ctx.total,
                        "name": seed.name,
                        "error": str(exc),
                        "elapsed": round(elapsed, 1),
                        "message": f"[{idx}/{ctx.total}] Failed: {seed.name} — {exc}",
                    },
                }
            )
            return (False, False)
        else:
            return (True, True)


async def run_seed(
    *,
    user_id: UUID,
    stream_repo: Any,
    control_set_repo: Any,
    site_id: str | None = None,
) -> AsyncIterator[JSONObject]:
    """Create seed strategies and control sets, yielding SSE progress events.

    Seeds run concurrently (up to ``_MAX_CONCURRENT_SEEDS`` at a time).
    Progress events are streamed back via an ``asyncio.Queue``.

    If *site_id* is provided, only seeds for that database are created.
    Otherwise all available seeds are used.

    """
    seeds = get_seeds_for_site(site_id) if site_id else get_all_seeds()
    total = len(seeds)
    yield {
        "type": "seed_progress",
        "data": {
            "phase": "starting",
            "message": f"Seeding {total} strategies and control sets (up to {_MAX_CONCURRENT_SEEDS} concurrent)...",
        },
    }

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_SEEDS)
    queue: asyncio.Queue[JSONObject | None] = asyncio.Queue()
    run_ctx = _SeedRunContext(
        total=total,
        semaphore=semaphore,
        queue=queue,
        stream_repo=stream_repo,
        control_set_repo=control_set_repo,
        user_id=user_id,
    )

    async def _run_all() -> list[tuple[bool, bool]]:
        """Launch all seeds concurrently, signal completion via sentinel."""
        results: list[tuple[bool, bool]] = []
        try:
            async with asyncio.TaskGroup() as tg:
                tasks = [
                    tg.create_task(_process_single_seed(i, seed, run_ctx))
                    for i, seed in enumerate(seeds)
                ]
            results = [t.result() for t in tasks]
        except BaseException:
            logger.exception("Unexpected error in seed TaskGroup")
        finally:
            await queue.put(None)
        return results

    runner = asyncio.create_task(_run_all())

    while True:
        event = await queue.get()
        if event is None:
            break
        yield event

    results = await runner
    strategies_ok = sum(1 for s, _ in results if s)
    control_sets_ok = sum(1 for _, c in results if c)

    yield {
        "type": "seed_complete",
        "data": {
            "total": total,
            "strategiesCreated": strategies_ok,
            "controlSetsCreated": control_sets_ok,
            "failed": total - strategies_ok,
            "message": (
                f"Seeding complete: {strategies_ok}/{total} strategies, "
                f"{control_sets_ok}/{total} control sets"
            ),
        },
    }
