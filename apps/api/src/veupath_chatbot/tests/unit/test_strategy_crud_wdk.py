"""Integration tests for strategy CRUD wire format (strategy_api/strategies.py).

Uses respx to mock WDK HTTP and verify:
- create_strategy: payload shape with stepTree serialization
- get_strategy: Pydantic parsing of WDK response into WDKStrategyDetails
- list_strategies: graceful degradation on unparseable items
- update_strategy: step-tree PUT + name PATCH

WDK contracts validated:
- Strategy creation payload: {name, stepTree, isPublic, isSaved, description?}
- StepTree serialization: {stepId, primaryInput?, secondaryInput?}
- get_strategy response: WDKStrategyDetails with stepTree, steps dict, validation
- Steps dict keyed by string IDs (not ints)
- list_strategies: partial failures → graceful skip
"""

import json
from dataclasses import dataclass, field
from typing import Any

import pytest
import respx

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.integrations.veupathdb.strategy_api.strategies import (
    StrategiesMixin,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKStepTree
from veupath_chatbot.platform.errors import DataParsingError


# ---------------------------------------------------------------------------
# Inline WDK response factories (verified against live PlasmoDB)
# ---------------------------------------------------------------------------
@dataclass
class _StrategyItemDetails:
    """Optional details for _strategy_list_item."""

    record_class_name: str = "TranscriptRecordClasses.TranscriptRecordClass"
    estimated_size: int = 150
    is_saved: bool = False
    signature: str = "abc123def456"
    leaf_and_transform_step_count: int = field(default=1)


def _strategy_get_response(
    strategy_id: int = 200,
    step_ids: list[int] | None = None,
) -> dict[str, Any]:
    """GET /users/{userId}/strategies/{strategyId} -- detailed strategy."""
    ids = step_ids or [100, 101, 102]
    search_names = {0: "GenesByTaxon", 1: "GenesByTextSearch", 2: "GenesByOrthologs"}

    def _build_tree(remaining: list[int]) -> dict[str, Any]:
        if len(remaining) == 1:
            return {"stepId": remaining[0]}
        return {
            "stepId": remaining[-1],
            "primaryInput": _build_tree(remaining[:-1]),
        }

    steps: dict[str, dict[str, Any]] = {}
    for idx, sid in enumerate(ids):
        sname = search_names.get(idx, "GenesByTaxon")
        steps[str(sid)] = {
            "id": sid,
            "searchName": sname,
            "searchConfig": {
                "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
                "wdkWeight": 0,
            },
            "displayName": "Organism" if sname == "GenesByTaxon" else sname,
            "customName": None,
            "estimatedSize": 150,
            "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
            "isFiltered": False,
            "hasCompleteStepAnalyses": False,
        }

    return {
        "strategyId": strategy_id,
        "name": "Test strategy",
        "description": "",
        "author": "Guest User",
        "organization": "",
        "releaseVersion": "68",
        "isSaved": False,
        "isPublic": False,
        "isDeleted": False,
        "isValid": True,
        "isExample": False,
        "rootStepId": ids[-1],
        "estimatedSize": 150,
        "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "stepTree": _build_tree(ids),
        "steps": steps,
        "signature": "abc123def456",
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-06T00:00:00Z",
        "lastViewed": "2026-03-06T00:00:00Z",
        "leafAndTransformStepCount": len(ids),
        "nameOfFirstStep": "Organism",
    }


def _strategy_list_item(
    strategy_id: int = 200,
    name: str = "Test strategy",
    details: _StrategyItemDetails | None = None,
) -> dict[str, Any]:
    """GET /users/{id}/strategies list item -- summary only."""
    d = details or _StrategyItemDetails()
    return {
        "strategyId": strategy_id,
        "name": name,
        "description": "",
        "author": "Guest User",
        "rootStepId": 100,
        "recordClassName": d.record_class_name,
        "signature": d.signature,
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-06T00:00:00Z",
        "lastViewed": "2026-03-06T00:00:00Z",
        "releaseVersion": "68",
        "isPublic": False,
        "isSaved": d.is_saved,
        "isValid": True,
        "isDeleted": False,
        "isExample": False,
        "organization": "",
        "estimatedSize": d.estimated_size,
        "nameOfFirstStep": "Organism",
        "leafAndTransformStepCount": d.leaf_and_transform_step_count,
    }

BASE = "https://plasmodb.org/plasmo/service"


class _TestableStrategies(StrategiesMixin, StrategyAPIBase):
    """Combine mixin with base for testing."""


@pytest.fixture
def api() -> _TestableStrategies:
    client = VEuPathDBClient(base_url=BASE, timeout=5.0)
    return _TestableStrategies(client=client, user_id="12345")


def _realistic_wdk_strategy(strategy_id: int = 200) -> dict:
    """Realistic WDK strategy response from the verified fixture catalog.

    Uses _strategy_get_response() which mirrors real PlasmoDB API output
    (verified 2026-03-06). This catches fixture drift that hand-built
    dicts would miss.
    """
    return _strategy_get_response(strategy_id=strategy_id, step_ids=[100])


# ── create_strategy ───────────────────────────────────────────────


class TestCreateStrategyPayload:
    """Verifies strategy creation payload matches WDK REST API."""

    @pytest.mark.asyncio
    async def test_payload_shape(self, api: _TestableStrategies) -> None:
        with respx.mock:
            route = respx.post(f"{BASE}/users/12345/strategies").respond(
                200, json={"id": 200}
            )
            step_tree = WDKStepTree(step_id=100)
            await api.create_strategy(step_tree, name="My Strategy")

            body = json.loads(route.calls[0].request.content)
            assert body["name"] == "My Strategy"
            assert body["stepTree"] == {"stepId": 100}
            assert body["isPublic"] is False
            assert body["isSaved"] is False

    @pytest.mark.asyncio
    async def test_nested_step_tree_serialization(
        self, api: _TestableStrategies
    ) -> None:
        """Step tree with primary+secondary inputs serialized correctly."""
        with respx.mock:
            route = respx.post(f"{BASE}/users/12345/strategies").respond(
                200, json={"id": 200}
            )
            left = WDKStepTree(step_id=100)
            right = WDKStepTree(step_id=101)
            root = WDKStepTree(step_id=102, primary_input=left, secondary_input=right)
            await api.create_strategy(root, name="Combined")

            body = json.loads(route.calls[0].request.content)
            tree = body["stepTree"]
            assert tree["stepId"] == 102
            assert tree["primaryInput"]["stepId"] == 100
            assert tree["secondaryInput"]["stepId"] == 101

    @pytest.mark.asyncio
    async def test_description_included_when_provided(
        self, api: _TestableStrategies
    ) -> None:
        with respx.mock:
            route = respx.post(f"{BASE}/users/12345/strategies").respond(
                200, json={"id": 200}
            )
            await api.create_strategy(
                WDKStepTree(step_id=100),
                name="Test",
                description="A detailed description",
            )
            body = json.loads(route.calls[0].request.content)
            assert body["description"] == "A detailed description"


# ── get_strategy ──────────────────────────────────────────────────


class TestGetStrategy:
    """Verifies WDK response → WDKStrategyDetails parsing."""

    @pytest.mark.asyncio
    async def test_parses_valid_response(self, api: _TestableStrategies) -> None:
        with respx.mock:
            respx.get(f"{BASE}/users/12345/strategies/200").respond(
                200, json=_realistic_wdk_strategy()
            )
            strategy = await api.get_strategy(200)
            assert strategy.strategy_id == 200
            assert strategy.root_step_id == 100
            assert strategy.is_saved is False
            # Steps dict keyed by string IDs
            assert "100" in strategy.steps

    @pytest.mark.asyncio
    async def test_step_has_estimated_size(self, api: _TestableStrategies) -> None:
        """WDK step.estimatedSize → used for result counts."""
        with respx.mock:
            respx.get(f"{BASE}/users/12345/strategies/200").respond(
                200, json=_realistic_wdk_strategy()
            )
            strategy = await api.get_strategy(200)
            step = strategy.steps["100"]
            # Realistic fixture uses estimatedSize=150 (from strategy_get_response)
            assert step.estimated_size == 150

    @pytest.mark.asyncio
    async def test_malformed_response_raises(self, api: _TestableStrategies) -> None:
        """Schema drift → DataParsingError."""
        with respx.mock:
            respx.get(f"{BASE}/users/12345/strategies/999").respond(
                200, json={"completely": "wrong"}
            )
            with pytest.raises(DataParsingError, match="Unexpected WDK strategy"):
                await api.get_strategy(999)


# ── list_strategies ───────────────────────────────────────────────


class TestListStrategies:
    @pytest.mark.asyncio
    async def test_parses_valid_items(self, api: _TestableStrategies) -> None:
        """Uses realistic inline WDK response fixture (verified against live API)."""
        with respx.mock:
            respx.get(f"{BASE}/users/12345/strategies").respond(
                200,
                json=[
                    _strategy_list_item(
                        strategy_id=100,
                        name="Strategy A",
                        details=_StrategyItemDetails(estimated_size=500),
                    )
                ],
            )
            strategies = await api.list_strategies()
            assert len(strategies) == 1
            assert strategies[0].strategy_id == 100
            assert strategies[0].name == "Strategy A"

    @pytest.mark.asyncio
    async def test_skips_unparseable_items(self, api: _TestableStrategies) -> None:
        """Graceful degradation: bad items skipped, valid ones returned."""
        with respx.mock:
            respx.get(f"{BASE}/users/12345/strategies").respond(
                200,
                json=[
                    _strategy_list_item(strategy_id=100, name="Valid"),
                    {"garbage": True},
                ],
            )
            strategies = await api.list_strategies()
            assert len(strategies) == 1

    @pytest.mark.asyncio
    async def test_non_list_response_returns_empty(
        self, api: _TestableStrategies
    ) -> None:
        with respx.mock:
            respx.get(f"{BASE}/users/12345/strategies").respond(
                200, json={"error": "unexpected"}
            )
            strategies = await api.list_strategies()
            assert strategies == []


# ── update_strategy ───────────────────────────────────────────────


class TestUpdateStrategy:
    @pytest.mark.asyncio
    async def test_step_tree_sent_via_put(self, api: _TestableStrategies) -> None:
        """Step tree update uses PUT on /step-tree endpoint (not PATCH)."""
        with respx.mock:
            put_route = respx.put(
                f"{BASE}/users/12345/strategies/200/step-tree"
            ).respond(200)
            respx.get(f"{BASE}/users/12345/strategies/200").respond(
                200, json=_realistic_wdk_strategy()
            )
            new_tree = WDKStepTree(step_id=999)
            await api.update_strategy(200, step_tree=new_tree)

            assert put_route.called
            body = json.loads(put_route.calls[0].request.content)
            assert body["stepTree"]["stepId"] == 999

    @pytest.mark.asyncio
    async def test_name_sent_via_patch(self, api: _TestableStrategies) -> None:
        """Name update uses PATCH on strategy endpoint."""
        with respx.mock:
            patch_route = respx.patch(f"{BASE}/users/12345/strategies/200").respond(200)
            respx.get(f"{BASE}/users/12345/strategies/200").respond(
                200, json=_realistic_wdk_strategy()
            )
            await api.update_strategy(200, name="New Name")

            assert patch_route.called
            body = json.loads(patch_route.calls[0].request.content)
            assert body["name"] == "New Name"
