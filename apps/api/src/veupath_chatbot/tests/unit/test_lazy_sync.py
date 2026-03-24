"""Unit tests for lazy WDK sync functions.

Tests for ``plan_needs_detail_fetch`` — a pure function that determines whether
a WDK-linked projection needs its full detail fetched from WDK.

These tests are TDD RED phase: they import functions that do not yet exist
and will fail with ImportError until the implementation is written.
"""

from dataclasses import dataclass, field

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.wdk_sync import plan_needs_detail_fetch


@dataclass
class FakeProjection:
    """Minimal stand-in for StreamProjection with the two fields plan_needs_detail_fetch reads."""

    wdk_strategy_id: int | None = None
    plan: JSONObject | None = field(default_factory=dict)


class TestPlanNeedsDetailFetch:
    """plan_needs_detail_fetch checks if a WDK-linked projection needs a detail fetch."""

    def test_empty_plan_needs_fetch(self) -> None:
        """Projection with empty plan ({}) needs a detail fetch."""
        proj = FakeProjection(wdk_strategy_id=123, plan={})
        assert plan_needs_detail_fetch(proj) is True

    def test_none_plan_needs_fetch(self) -> None:
        """Projection with None plan needs a detail fetch."""
        proj = FakeProjection(wdk_strategy_id=123, plan=None)
        assert plan_needs_detail_fetch(proj) is True

    def test_plan_without_root_needs_fetch(self) -> None:
        """Projection with plan missing 'root' key needs a detail fetch."""
        proj = FakeProjection(wdk_strategy_id=123, plan={"recordType": "transcript"})
        assert plan_needs_detail_fetch(proj) is True

    def test_populated_plan_does_not_need_fetch(self) -> None:
        """Projection with a real plan (has 'root') does NOT need a detail fetch."""
        proj = FakeProjection(
            wdk_strategy_id=123,
            plan={
                "recordType": "transcript",
                "root": {"searchName": "GenesByTaxon", "id": "1"},
            },
        )
        assert plan_needs_detail_fetch(proj) is False

    def test_local_strategy_never_needs_fetch(self) -> None:
        """Projection without wdk_strategy_id (local) never needs WDK fetch."""
        proj = FakeProjection(wdk_strategy_id=None, plan={})
        assert plan_needs_detail_fetch(proj) is False

    def test_local_strategy_with_plan_does_not_need_fetch(self) -> None:
        """Local strategy with a plan doesn't need fetch."""
        proj = FakeProjection(
            wdk_strategy_id=None,
            plan={"recordType": "gene", "root": {"searchName": "GenesByTaxon"}},
        )
        assert plan_needs_detail_fetch(proj) is False
