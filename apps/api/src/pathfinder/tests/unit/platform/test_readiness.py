"""Tests for the ReadinessState model."""

import pytest

from pathfinder.platform.readiness import (
    ReadinessState,
    SubsystemStatus,
    get_readiness,
    reset_readiness,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_readiness()


class TestSubsystemStatus:
    def test_default_not_ready(self) -> None:
        status = SubsystemStatus()
        assert status.ready is False
        assert status.error is None

    def test_ready_with_no_error(self) -> None:
        status = SubsystemStatus(ready=True)
        assert status.ready is True
        assert status.error is None

    def test_error_implies_not_ready(self) -> None:
        status = SubsystemStatus(ready=False, error="boom")
        assert status.ready is False
        assert status.error == "boom"


class TestReadinessState:
    def test_fresh_state_is_not_ready(self) -> None:
        state = ReadinessState()
        assert state.all_ready is False
        assert "database" in state.not_ready
        assert "embedding_backend" in state.not_ready
        assert "piguard" in state.not_ready

    def test_all_ready_requires_every_subsystem(self) -> None:
        state = ReadinessState()
        state.mark_ready("database")
        state.mark_ready("embedding_backend")
        state.mark_ready("piguard")
        state.mark_ready("graph_checkpointer")
        assert state.all_ready is True
        assert state.not_ready == []

    def test_catalog_participation(self) -> None:
        state = ReadinessState()
        state.mark_ready("database")
        state.mark_ready("embedding_backend")
        state.mark_ready("piguard")
        state.mark_ready("graph_checkpointer")
        state.register_catalog("plasmodb")
        state.register_catalog("toxodb")
        assert state.all_ready is False
        assert "catalog:plasmodb" in state.not_ready
        assert "catalog:toxodb" in state.not_ready

        state.mark_catalog_ready("plasmodb")
        assert state.all_ready is False
        state.mark_catalog_ready("toxodb")
        assert state.all_ready is True

    def test_mark_failed_sets_error_and_keeps_not_ready(self) -> None:
        state = ReadinessState()
        state.mark_failed("database", "connection refused")
        assert state.database.ready is False
        assert state.database.error == "connection refused"
        assert "database" in state.not_ready

    def test_unknown_subsystem_raises(self) -> None:
        state = ReadinessState()
        with pytest.raises(ValueError, match="unknown"):
            state.mark_ready("does_not_exist")

    def test_singleton_returns_same_instance(self) -> None:
        a = get_readiness()
        b = get_readiness()
        assert a is b

    def test_reset_clears_state(self) -> None:
        state = get_readiness()
        state.mark_ready("database")
        assert state.database.ready is True
        reset_readiness()
        assert get_readiness().database.ready is False
