"""Seed strategy runner.

Creates real WDK strategies (visible in the sidebar) and curated control sets
(available in the Experiments tab) across multiple VEuPathDB sites.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.seed.definitions import SEEDS

logger = get_logger(__name__)


async def run_seed(
    *,
    user_id: UUID,
    strategy_repo: Any,
    control_set_repo: Any,
) -> AsyncIterator[JSONObject]:
    """Create seed strategies and control sets, yielding SSE progress events.

    For each :class:`SeedDef`:
    1. Create a WDK strategy via ``_materialize_step_tree`` + ``create_strategy``
    2. Sync the strategy to the user's sidebar via ``_sync_single_wdk_strategy``
    3. Create a control set via ``control_set_repo.create``

    Imports are deferred to avoid circular dependencies.
    """
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
    from veupath_chatbot.services.experiment.materialization import (
        _materialize_step_tree,
    )
    from veupath_chatbot.transport.http.routers.strategies.wdk_import import (
        _sync_single_wdk_strategy,
    )

    total = len(SEEDS)
    yield {
        "type": "seed_progress",
        "data": {
            "phase": "starting",
            "message": f"Seeding {total} strategies and control sets...",
        },
    }

    strategies_ok = 0
    control_sets_ok = 0

    for i, seed in enumerate(SEEDS):
        idx = i + 1
        yield {
            "type": "seed_progress",
            "data": {
                "phase": "running",
                "current": idx,
                "total": total,
                "name": seed.name,
                "message": f"[{idx}/{total}] Creating strategy: {seed.name}",
            },
        }

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
            wdk_strategy_id: int | None = None
            if isinstance(created, dict):
                raw = created.get("id")
                if isinstance(raw, int):
                    wdk_strategy_id = raw

            if wdk_strategy_id is None:
                raise ValueError(f"WDK did not return a strategy ID for '{seed.name}'")

            # 3. Sync to local DB (sidebar)
            await _sync_single_wdk_strategy(
                wdk_id=wdk_strategy_id,
                site_id=seed.site_id,
                api=api,
                strategy_repo=strategy_repo,
                user_id=user_id,
            )
            strategies_ok += 1

            elapsed_strategy = time.monotonic() - t0
            yield {
                "type": "seed_strategy_complete",
                "data": {
                    "current": idx,
                    "total": total,
                    "name": seed.name,
                    "wdkStrategyId": wdk_strategy_id,
                    "elapsed": round(elapsed_strategy, 1),
                    "message": (f"[{idx}/{total}] Strategy created: {seed.name}"),
                },
            }

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
            control_sets_ok += 1

        except Exception as exc:
            elapsed = time.monotonic() - t0
            logger.error("Seed failed", name=seed.name, error=str(exc))
            yield {
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
