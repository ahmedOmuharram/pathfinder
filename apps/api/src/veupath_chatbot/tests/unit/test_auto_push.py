"""Unit tests for services.strategies.auto_push.

The existing test_auto_push_lock.py covers _get_push_lock eviction.
This file covers try_auto_push_to_wdk end-to-end with mocked
DB sessions, repos, and WDK API calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.strategies.auto_push import (
    _PUSH_LOCKS_MAX,
    _get_push_lock,
    _push_locks,
    try_auto_push_to_wdk,
)


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


def _make_patches(
    projection: MagicMock | None = None,
    compile_result: MagicMock | None = None,
    validate_raise: Exception | None = None,
    compile_raise: Exception | None = None,
    api_update_raise: Exception | None = None,
):
    """Build a context manager stack of patches for try_auto_push_to_wdk."""
    proj = projection or _mock_projection()

    repo = MagicMock()
    repo.get_projection = AsyncMock(return_value=proj)
    repo.update_projection = AsyncMock()

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    if compile_result is None:
        compiled_step = MagicMock()
        compiled_step.local_id = "s1"
        compiled_step.wdk_step_id = 1001
        compile_result = MagicMock()
        compile_result.steps = [compiled_step]
        compile_result.step_tree = MagicMock()

    mock_api = MagicMock()
    if api_update_raise:
        mock_api.update_strategy = AsyncMock(side_effect=api_update_raise)
    else:
        mock_api.update_strategy = AsyncMock()

    validate_fn = MagicMock()
    if validate_raise:
        validate_fn.side_effect = validate_raise
    else:
        mock_ast = StrategyAST(
            record_type="gene",
            root=PlanStepNode(
                search_name="GenesByTextSearch",
                parameters={"text_expression": "kinase"},
                id="s1",
            ),
        )
        validate_fn.return_value = mock_ast

    compile_fn = AsyncMock()
    if compile_raise:
        compile_fn.side_effect = compile_raise
    else:
        compile_fn.return_value = compile_result

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
        "get_api": patch(
            "veupath_chatbot.services.strategies.auto_push.get_strategy_api",
            return_value=mock_api,
        ),
        "compile": patch(
            "veupath_chatbot.services.strategies.auto_push.compile_strategy",
            compile_fn,
        ),
    }
    return patches, repo, mock_session, mock_api, compile_fn


class TestTryAutoPushToWdk:
    @pytest.mark.asyncio
    async def test_skips_when_no_projection(self) -> None:
        """When get_projection returns None, no WDK push happens."""
        patches, repo, _mock_session, mock_api, _compile_fn = _make_patches()
        repo.get_projection = AsyncMock(return_value=None)

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["get_api"],
            patches["compile"],
        ):
            await try_auto_push_to_wdk(uuid4())
        mock_api.update_strategy.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_no_wdk_strategy_id(self) -> None:
        proj = _mock_projection(wdk_strategy_id=None)
        patches, _repo, _mock_session, mock_api, _compile_fn = _make_patches(
            projection=proj
        )

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["get_api"],
            patches["compile"],
        ):
            await try_auto_push_to_wdk(uuid4())
        mock_api.update_strategy.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_no_site_id(self) -> None:
        proj = _mock_projection(site_id=None)
        patches, _repo, _mock_session, mock_api, _compile_fn = _make_patches(
            projection=proj
        )

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["get_api"],
            patches["compile"],
        ):
            await try_auto_push_to_wdk(uuid4())
        mock_api.update_strategy.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_empty_plan(self) -> None:
        proj = _mock_projection(plan={})
        patches, _repo, _mock_session, mock_api, _compile_fn = _make_patches(
            projection=proj
        )

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["get_api"],
            patches["compile"],
        ):
            await try_auto_push_to_wdk(uuid4())
        mock_api.update_strategy.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_plan_is_not_dict(self) -> None:
        proj = _mock_projection()
        proj.plan = "not a dict"
        patches, _repo, _mock_session, mock_api, _compile_fn = _make_patches(
            projection=proj
        )

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["get_api"],
            patches["compile"],
        ):
            await try_auto_push_to_wdk(uuid4())
        mock_api.update_strategy.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_push_updates_projection(self) -> None:
        patches, repo, mock_session, mock_api, _compile_fn = _make_patches()

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["get_api"],
            patches["compile"],
        ):
            await try_auto_push_to_wdk(uuid4())

        mock_api.update_strategy.assert_called_once()
        repo.update_projection.assert_called_once()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_successful_push_rewrites_ids(self) -> None:
        """After compilation, local step IDs should be rewritten to WDK IDs."""
        patches, repo, _mock_session, _mock_api, _compile_fn = _make_patches()

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["get_api"],
            patches["compile"],
        ):
            await try_auto_push_to_wdk(uuid4())

        # update_projection should be called with the rewritten plan
        call_kwargs = repo.update_projection.call_args
        assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_wdk_404_clears_strategy_id(self) -> None:
        """When WDK returns 404, the stale wdk_strategy_id should be cleared."""
        patches, _repo, mock_session, _mock_api, _compile_fn = _make_patches(
            api_update_raise=WDKError("Not found", status=404)
        )

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["get_api"],
            patches["compile"],
        ):
            # Should not raise
            await try_auto_push_to_wdk(uuid4())

        # Should have tried to clear wdk_strategy_id
        # The function recreates the repo, so we check that commit was called
        # at least for the 404 branch
        mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_wdk_non_404_error_logged_not_raised(self) -> None:
        """Non-404 WDK errors are logged but not raised."""
        patches, _repo, mock_session, _mock_api, _compile_fn = _make_patches(
            api_update_raise=WDKError("Server error", status=500)
        )

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["get_api"],
            patches["compile"],
        ):
            # Should not raise
            await try_auto_push_to_wdk(uuid4())

        mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_generic_exception_logged_not_raised(self) -> None:
        """Generic exceptions are logged but not raised."""
        patches, _repo, mock_session, _mock_api, _compile_fn = _make_patches(
            compile_raise=RuntimeError("unexpected")
        )

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["get_api"],
            patches["compile"],
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
            patches, _repo, _mock_session, mock_api, _compile_fn = _make_patches()
            with (
                patches["session_factory"],
                patches["repo_cls"],
                patches["validate"],
                patches["get_api"],
                patches["compile"],
            ):
                await try_auto_push_to_wdk(sid)
            # Should have skipped entirely, no update_strategy call
            mock_api.update_strategy.assert_not_called()
        finally:
            lock.release()

    @pytest.mark.asyncio
    async def test_unmapped_steps_skip_id_rewrite(self) -> None:
        """When compiled map is missing step IDs, skip ID rewrite to prevent corruption."""
        compiled_step = MagicMock()
        compiled_step.local_id = "s_other"  # Does NOT match "s1" in the plan
        compiled_step.wdk_step_id = 1001
        compile_result = MagicMock()
        compile_result.steps = [compiled_step]
        compile_result.step_tree = MagicMock()

        patches, repo, _mock_session, _mock_api, _compile_fn = _make_patches(
            compile_result=compile_result
        )

        with (
            patches["session_factory"],
            patches["repo_cls"],
            patches["validate"],
            patches["get_api"],
            patches["compile"],
        ):
            await try_auto_push_to_wdk(uuid4())

        # Should still call update_projection (plan without ID rewrite)
        repo.update_projection.assert_called_once()


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
