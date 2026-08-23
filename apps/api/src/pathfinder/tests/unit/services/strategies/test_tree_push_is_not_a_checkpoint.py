"""A step tree WDK accepts is not a strategy WDK can run.

The tree write validates structure only. Whether the steps run is answered by
the read that follows it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from assistant_core.platform.types import JSONObject
from pydantic import JsonValue

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.graph_model import flatten_tree
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKIdentifier,
    WDKStep,
    WDKStepTree,
    WDKStrategyDetails,
)
from pathfinder.services.strategies.sync import sync_strategy
from pathfinder.services.strategies.sync_state import WDKSyncState

_WDK_STEP_ID = 1001


def _invalid_step() -> WDKStep:
    return WDKStep.model_validate(
        {
            "id": _WDK_STEP_ID,
            "searchName": "GenesByMolecularWeight",
            "searchConfig": {"parameters": {"min_molecular_weight": "abc"}},
            "estimatedSize": None,
            "validation": {
                "level": "RUNNABLE",
                "isValid": False,
                "errors": {
                    "general": [],
                    "byKey": {"min_molecular_weight": ["Not a number."]},
                },
            },
        }
    )


@dataclass
class _RecordingAPI:
    """Accepts any tree and answers the read with an invalid step."""

    calls: list[str] = field(default_factory=list)

    async def create_strategy(
        self,
        step_tree: WDKStepTree,
        name: str,
        description: str | None = None,
        *,
        is_public: bool = False,
        is_saved: bool = False,
    ) -> WDKIdentifier:
        del step_tree, name, description, is_public, is_saved
        self.calls.append("create_strategy")
        return WDKIdentifier(id=77)

    async def update_strategy(
        self,
        strategy_id: int,
        step_tree: WDKStepTree | None = None,
        name: str | None = None,
    ) -> WDKStrategyDetails:
        del strategy_id, step_tree, name
        self.calls.append("update_strategy")
        raise NotImplementedError

    async def get_strategy(self, strategy_id: int) -> WDKStrategyDetails:
        del strategy_id
        self.calls.append("get_strategy")
        return WDKStrategyDetails.model_validate(
            {
                "strategyId": 77,
                "rootStepId": _WDK_STEP_ID,
                "name": "test",
                "stepTree": {"stepId": _WDK_STEP_ID},
                "steps": {str(_WDK_STEP_ID): _invalid_step().model_dump(by_alias=True)},
                "recordClassName": "transcript",
            }
        )

    async def set_step_filter(
        self,
        step_id: int,
        filter_name: str,
        value: JsonValue,
        *,
        disabled: bool = False,
    ) -> None:
        del step_id, filter_name, value, disabled
        self.calls.append("set_step_filter")

    async def run_step_analysis(
        self,
        step_id: int,
        analysis_type: str,
        parameters: JSONObject | None = None,
        custom_name: str | None = None,
    ) -> JSONObject:
        del step_id, analysis_type, parameters, custom_name
        self.calls.append("run_step_analysis")
        return {}

    async def run_step_report(
        self, step_id: int, report_name: str, config: JSONObject | None = None
    ) -> JsonValue:
        del step_id, report_name, config
        self.calls.append("run_step_report")
        return None


class _Site:
    def strategy_url(self, strategy_id: int, root_step_id: int | None = None) -> str:
        return f"https://example.invalid/s/{strategy_id}/{root_step_id}"


def _graph() -> StrategyGraph:
    graph = StrategyGraph("g1", "test", "plasmodb")
    graph.steps = flatten_tree(
        StrategyStepNode(id="A", search_name="GenesByMolecularWeight")
    )
    graph.record_type = "transcript"
    graph.recompute_roots()
    return graph


async def _sync(api: _RecordingAPI) -> object:
    return await sync_strategy(
        graph=_graph(),
        sync_state=WDKSyncState(wdk_step_ids={"A": _WDK_STEP_ID}),
        api=api,
        site=_Site(),
        site_id="plasmodb",
    )


class TestTheWriteIsFollowedByARead:
    @pytest.mark.asyncio
    async def test_the_strategy_is_read_back(self) -> None:
        api = _RecordingAPI()

        await _sync(api)

        assert "get_strategy" in api.calls

    @pytest.mark.asyncio
    async def test_the_read_happens_after_the_write(self) -> None:
        api = _RecordingAPI()

        await _sync(api)

        assert api.calls.index("create_strategy") < api.calls.index("get_strategy")


class TestTheReadIsWhatReportsValidity:
    @pytest.mark.asyncio
    async def test_an_accepted_tree_can_still_hold_an_invalid_step(self) -> None:
        # The write raised nothing; the step is unrunnable all the same.
        sync_state = WDKSyncState(wdk_step_ids={"A": _WDK_STEP_ID})

        await sync_strategy(
            graph=_graph(),
            sync_state=sync_state,
            api=_RecordingAPI(),
            site=_Site(),
            site_id="plasmodb",
        )

        assert sync_state.step_validations["A"].rejects()

    @pytest.mark.asyncio
    async def test_the_rejection_message_is_kept(self) -> None:
        sync_state = WDKSyncState(wdk_step_ids={"A": _WDK_STEP_ID})

        await sync_strategy(
            graph=_graph(),
            sync_state=sync_state,
            api=_RecordingAPI(),
            site=_Site(),
            site_id="plasmodb",
        )

        assert "Not a number." in " ".join(sync_state.step_validations["A"].messages())

    def test_a_validation_that_was_never_checked_does_not_claim_validity(self) -> None:
        assert StepValidation(level="NONE", is_valid=False).was_checked() is False
