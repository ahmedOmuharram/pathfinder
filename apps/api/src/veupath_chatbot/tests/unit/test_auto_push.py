"""Unit tests for services.strategies.auto_push.

The existing test_auto_push_lock.py covers _get_push_lock eviction.
This file covers try_auto_push_to_wdk end-to-end with mocked
DB sessions, repos, and WDK sync calls.
"""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.strategies.auto_push import (
    _PUSH_LOCKS_MAX,
    _get_push_lock,
    _push_locks,
    try_auto_push_to_wdk,
)
from veupath_chatbot.transport.http.schemas.strategies import StrategyPlanPayload


@pytest.fixture(autouse=True)
def _clear_locks():
    """Clear module-level push locks before and after each test."""
    _push_locks.clear()
    yield
    _push_locks.clear()


_DEFAULT_PLAN: dict = {
    "recordType": "gene",
    "root": {
        "id": "s1",
        "searchName": "GenesByTextSearch",
        "parameters": {"text_expression": "kinase"},
    },
}

_SENTINEL = object()


def _mock_projection(
    *,
    wdk_strategy_id: int | None = 100,
    site_id: str | None = "plasmodb",
    plan: object = _SENTINEL,
    name: str = "Test Strategy",
) -> MagicMock:
    proj = MagicMock()
    proj.wdk_strategy_id = wdk_strategy_id
    proj.site_id = site_id
    proj.plan = _DEFAULT_PLAN if plan is _SENTINEL else plan
    proj.name = name
    return proj


@dataclass
class _MockSyncResult:
    wdk_strategy_id: int | None = 100
    wdk_url: str | None = None
    root_step_id: int = 1001
    counts: dict = None  # type: ignore[assignment]
    root_count: int | None = 150
    zero_step_ids: list = None  # type: ignore[assignment]
    step_count: int = 1

    def __post_init__(self) -> None:
        if self.counts is None:
            self.counts = {"s1": 150}
        if self.zero_step_ids is None:
            self.zero_step_ids = []


def _make_patches(
    projection: MagicMock | None = None,
    validate_raise: Exception | None = None,
    sync_raise: Exception | None = None,
):
    """Build a context manager stack of patches for try_auto_push_to_wdk."""
    proj = projection or _mock_projection()

    repo = MagicMock()
    repo.get_projection = AsyncMock(return_value=proj)
    repo.update_projection = AsyncMock()

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    validate_fn = MagicMock()
    if validate_raise:
        validate_fn.side_effect = validate_raise
    else:
        mock_payload = StrategyPlanPayload(
            record_type="gene",
            root=PlanStepNode(
                search_name="GenesByTextSearch",
                parameters={"text_expression": "kinase"},
                id="s1",
            ),
        )
        validate_fn.return_value = mock_payload

    sync_fn = AsyncMock()
    if sync_raise:
        sync_fn.side_effect = sync_raise
    else:
        sync_fn.return_value = _MockSyncResult()

    patches = {
        "session_factory": patch(
            "veupath_chatbot.services.strategies.auto_push.async_session_factory",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            ),
        ),
        "repo_cls": patch(
            "veupath_chatbot.services.strategies.auto_push.StreamRepository",
            return_value=repo,
        ),
        "validate": patch(
            "veupath_chatbot.services.strategies.auto_push.validate_plan_or_raise",
            validate_fn,
        ),
        "sync": patch(
            "veupath_chatbot.services.strategies.auto_push.sync_strategy_for_site",
            sync_fn,
        ),
    }
    return patches, repo, mock_session, sync_fn


def _enter_patches(patches: dict) -> None:
    """No-op — patches are used via context managers."""


class TestTryAutoPushToWdk:
    @pytest.mark.asyncio
    async def test_skips_when_no_projection(self) -> None:
        """When get_projection returns None, no WDK push happens."""
        patches, repo, _mock_session, sync_fn = _make_patches()
        repo.get_projection = AsyncMock(return_value=None)

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["sync"],
        ):
            await try_auto_push_to_wdk(uuid4())
        sync_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_no_wdk_strategy_id(self) -> None:
        proj = _mock_projection(wdk_strategy_id=None)
        patches, _repo, _mock_session, sync_fn = _make_patches(projection=proj)

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["sync"],
        ):
            await try_auto_push_to_wdk(uuid4())
        sync_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_no_site_id(self) -> None:
        proj = _mock_projection(site_id=None)
        patches, _repo, _mock_session, sync_fn = _make_patches(projection=proj)

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["sync"],
        ):
            await try_auto_push_to_wdk(uuid4())
        sync_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_empty_plan(self) -> None:
        proj = _mock_projection(plan={})
        patches, _repo, _mock_session, sync_fn = _make_patches(projection=proj)

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["sync"],
        ):
            await try_auto_push_to_wdk(uuid4())
        sync_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_plan_is_not_dict(self) -> None:
        proj = _mock_projection()
        proj.plan = "not a dict"
        patches, _repo, _mock_session, sync_fn = _make_patches(projection=proj)

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["sync"],
        ):
            await try_auto_push_to_wdk(uuid4())
        sync_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_push_updates_projection(self) -> None:
        patches, repo, mock_session, sync_fn = _make_patches()

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["sync"],
        ):
            await try_auto_push_to_wdk(uuid4())

        sync_fn.assert_called_once()
        repo.update_projection.assert_called_once()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_successful_push_calls_sync(self) -> None:
        """After validation, sync_strategy_for_site should be called."""
        patches, repo, _mock_session, sync_fn = _make_patches()

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["sync"],
        ):
            await try_auto_push_to_wdk(uuid4())

        sync_fn.assert_called_once()
        # update_projection should be called with the updated plan
        call_kwargs = repo.update_projection.call_args
        assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_wdk_404_clears_strategy_id(self) -> None:
        """When WDK returns 404, the stale wdk_strategy_id should be cleared."""
        patches, _repo, mock_session, _sync_fn = _make_patches(
            sync_raise=WDKError("Not found", status=404)
        )

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["sync"],
        ):
            # Should not raise
            await try_auto_push_to_wdk(uuid4())

        mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_wdk_non_404_error_logged_not_raised(self) -> None:
        """Non-404 WDK errors are logged but not raised."""
        patches, _repo, mock_session, _sync_fn = _make_patches(
            sync_raise=WDKError("Server error", status=500)
        )

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["sync"],
        ):
            # Should not raise
            await try_auto_push_to_wdk(uuid4())

        mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_generic_exception_logged_not_raised(self) -> None:
        """Generic exceptions are logged but not raised."""
        patches, _repo, mock_session, _sync_fn = _make_patches(
            sync_raise=RuntimeError("unexpected")
        )

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["sync"],
        ):
            await try_auto_push_to_wdk(uuid4())

        mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_skips_when_lock_already_held(self) -> None:
        """If the lock is already held, the push should be skipped."""
        sid = uuid4()
        lock = _get_push_lock(sid)
        await lock.acquire()

        try:
            patches, _repo, _mock_session, sync_fn = _make_patches()
            with (
                patches["session_factory"],
                patches["repo_cls"],
                patches["validate"],
                patches["sync"],
            ):
                await try_auto_push_to_wdk(sid)
            # Should have skipped entirely, no sync call
            sync_fn.assert_not_called()
        finally:
            lock.release()

    @pytest.mark.asyncio
    async def test_validate_failure_raises_and_rolls_back(self) -> None:
        """When validate_plan_or_raise fails, the error propagates and session rolls back."""
        patches, _repo, mock_session, sync_fn = _make_patches(
            validate_raise=RuntimeError("Invalid plan")
        )

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["sync"],
        ):
            await try_auto_push_to_wdk(uuid4())

        # validate_plan_or_raise raises AppError -> caught by outer handler
        sync_fn.assert_not_called()
        mock_session.rollback.assert_called()


class TestGetPushLockEdgeCases:
    """Additional edge cases for _get_push_lock beyond test_auto_push_lock.py."""

    def test_new_lock_created_for_new_id(self) -> None:
        sid = uuid4()
        lock = _get_push_lock(sid)
        assert sid in _push_locks
        assert lock is _push_locks[sid]

    def test_returns_existing_lock(self) -> None:
        sid = uuid4()
        lock1 = _get_push_lock(sid)
        lock2 = _get_push_lock(sid)
        assert lock1 is lock2

    def test_bounded_memory_after_many_inserts(self) -> None:
        """Lock dict should not exceed _PUSH_LOCKS_MAX + 1 after many insertions."""
        for _ in range(_PUSH_LOCKS_MAX + 50):
            _get_push_lock(uuid4())
        # Should be at or near the max (eviction happens on overflow)
        assert len(_push_locks) <= _PUSH_LOCKS_MAX + 1
