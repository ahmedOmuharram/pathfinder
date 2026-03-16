"""Seed strategy runner.

Creates real WDK strategies (visible in the sidebar) and curated control sets
(available in the Experiments tab) across multiple VEuPathDB sites.

Seeds are processed concurrently across sites using ``asyncio.TaskGroup``,
with a semaphore to cap the number of parallel WDK requests.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.seed.seeds import (
    get_all_seeds,
    get_seeds_for_site,
)

logger = get_logger(__name__)

_MAX_CONCURRENT_SEEDS = 10


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

    Imports are deferred to avoid circular dependencies.
    """
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
    from veupath_chatbot.services.experiment.helpers import extract_wdk_id
    from veupath_chatbot.services.experiment.materialization import (
        _materialize_step_tree,
    )
    from veupath_chatbot.services.strategies.wdk_bridge import (
        sync_to_projection,
    )

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

    async def _seed_one(i: int, seed: Any) -> tuple[bool, bool]:
        """Process a single seed. Returns (strategy_ok, control_set_ok)."""
        idx = i + 1
        async with semaphore:
            await queue.put(
                {
                    "type": "seed_progress",
                    "data": {
                        "phase": "running",
                        "current": idx,
                        "total": total,
                        "name": seed.name,
                        "message": f"[{idx}/{total}] Creating strategy: {seed.name}",
                    },
                }
            )

            t0 = time.monotonic()
            try:
                api = get_strategy_api(seed.site_id)

                # 1. Materialize step tree into real WDK steps
                root_tree = await _materialize_step_tree(
                    api, seed.step_tree, seed.record_type
                )

                # 2. Create the WDK strategy (visible, not internal)
                created = await api.create_strategy(
                    step_tree=root_tree,
                    name=seed.name,
                    description=seed.description,
                    is_saved=True,
                )
                wdk_strategy_id = extract_wdk_id(created)

                if wdk_strategy_id is None:
                    raise ValueError(
                        f"WDK did not return a strategy ID for '{seed.name}'"
                    )

                # 3. Sync to local DB (sidebar)
                await sync_to_projection(
                    wdk_id=wdk_strategy_id,
                    site_id=seed.site_id,
                    api=api,
                    stream_repo=stream_repo,
                    user_id=user_id,
                )

                elapsed_strategy = time.monotonic() - t0
                await queue.put(
                    {
                        "type": "seed_strategy_complete",
                        "data": {
                            "current": idx,
                            "total": total,
                            "name": seed.name,
                            "wdkStrategyId": wdk_strategy_id,
                            "elapsed": round(elapsed_strategy, 1),
                            "message": f"[{idx}/{total}] Strategy created: {seed.name}",
                        },
                    }
                )

                # 4. Create control set
                cs = seed.control_set
                await control_set_repo.create(
                    name=cs.name,
                    site_id=seed.site_id,
                    record_type=seed.record_type,
                    positive_ids=cs.positive_ids,
                    negative_ids=cs.negative_ids,
                    source="curation",
                    tags=cs.tags,
                    provenance_notes=cs.provenance_notes,
                    is_public=True,
                    user_id=user_id,
                )
                return (True, True)

            except Exception as exc:
                elapsed = time.monotonic() - t0
                logger.error("Seed failed", name=seed.name, error=str(exc))
                await queue.put(
                    {
                        "type": "seed_item_error",
                        "data": {
                            "current": idx,
                            "total": total,
                            "name": seed.name,
                            "error": str(exc),
                            "elapsed": round(elapsed, 1),
                            "message": f"[{idx}/{total}] Failed: {seed.name} — {exc}",
                        },
                    }
                )
                return (False, False)

    async def _run_all() -> list[tuple[bool, bool]]:
        """Launch all seeds concurrently, signal completion via sentinel."""
        results: list[tuple[bool, bool]] = []
        try:
            async with asyncio.TaskGroup() as tg:
                tasks = [
                    tg.create_task(_seed_one(i, seed)) for i, seed in enumerate(seeds)
                ]
            results = [t.result() for t in tasks]
        except BaseException:
            # TaskGroup re-raises child exceptions; individual seeds already
            # catch their own, so this is a safeguard for truly unexpected errors.
            logger.exception("Unexpected error in seed TaskGroup")
        finally:
            await queue.put(None)
        return results

    runner = asyncio.create_task(_run_all())

    # Yield events as they arrive from concurrent tasks
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
