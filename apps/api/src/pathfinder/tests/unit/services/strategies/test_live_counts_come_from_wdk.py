"""The live side of a staleness check reads WDK, not the build's own cache.

An edit made in the graph editor, or on the site itself, moves the strategy
without touching the counts recorded at build time. Reading those counts back
as "live" compares the cache with itself, so no edit can ever be detected.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from pathfinder.integrations.veupathdb.wdk_models import WDKStrategyDetails
from pathfinder.services.strategies.live_counts import read_wdk_step_counts
from pathfinder.services.strategies.sync_state import WDKSyncState


def _details(sizes: dict[int, int | None]) -> WDKStrategyDetails:
    return WDKStrategyDetails.model_validate(
        {
            "strategyId": 900,
            "name": "s",
            "rootStepId": max(sizes),
            "stepTree": {"stepId": max(sizes)},
            "steps": {
                str(wdk_id): {
                    "id": wdk_id,
                    "searchName": "GenesByText",
                    "searchConfig": {"parameters": {}},
                    "estimatedSize": size,
                }
                for wdk_id, size in sizes.items()
            },
        }
    )


def _api(details: WDKStrategyDetails) -> Any:
    api = AsyncMock()
    api.get_strategy = AsyncMock(return_value=details)
    return api


def _sync_state(recorded: dict[str, int]) -> WDKSyncState:
    state = WDKSyncState()
    state.wdk_strategy_id = 900
    state.wdk_step_ids = {"leaf": 11, "root": 22}
    state.step_counts = dict(recorded)
    return state


class TestTheCountsComeFromTheServer:
    @pytest.mark.asyncio
    async def test_an_edited_step_reports_its_new_size(self) -> None:
        state = _sync_state({"leaf": 3259, "root": 15})

        counts = await read_wdk_step_counts(state, _api(_details({11: 897, 22: 3})))

        assert counts["leaf"] == 897

    @pytest.mark.asyncio
    async def test_the_root_reports_its_new_size(self) -> None:
        state = _sync_state({"leaf": 3259, "root": 15})

        counts = await read_wdk_step_counts(state, _api(_details({11: 897, 22: 3})))

        assert counts["root"] == 3

    @pytest.mark.asyncio
    async def test_the_recorded_counts_are_not_consulted(self) -> None:
        # Every recorded value differs from the server's, so a cache read
        # cannot produce this result by accident.
        state = _sync_state({"leaf": 1, "root": 2})

        counts = await read_wdk_step_counts(state, _api(_details({11: 897, 22: 3})))

        assert counts == {"leaf": 897, "root": 3}


class TestUnknownStaysUnknown:
    @pytest.mark.asyncio
    async def test_a_step_wdk_does_not_report_is_none(self) -> None:
        state = _sync_state({"leaf": 3259, "root": 15})

        counts = await read_wdk_step_counts(state, _api(_details({11: 897})))

        assert counts["root"] is None

    @pytest.mark.asyncio
    async def test_a_failed_read_yields_no_counts(self) -> None:
        # A WDK outage must not read as "every step changed".
        api = AsyncMock()
        api.get_strategy = AsyncMock(side_effect=OSError("wdk down"))

        assert await read_wdk_step_counts(_sync_state({"leaf": 1}), api) == {}

    @pytest.mark.asyncio
    async def test_an_unsynced_strategy_yields_no_counts(self) -> None:
        state = WDKSyncState()

        assert await read_wdk_step_counts(state, _api(_details({11: 897}))) == {}
