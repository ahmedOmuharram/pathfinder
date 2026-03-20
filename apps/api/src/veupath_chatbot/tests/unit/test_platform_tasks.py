"""Unit tests for platform.tasks — fire-and-forget background task helper."""

import asyncio
import concurrent.futures

from veupath_chatbot.platform.tasks import _background_tasks, spawn


class TestSpawn:
    async def test_spawn_creates_task_and_runs_it(self):
        result: list[str] = []

        async def work():
            result.append("done")

        task = spawn(work(), name="test-task")
        assert task is not None
        assert task.get_name() == "test-task"
        assert task in _background_tasks
        await task
        assert result == ["done"]

    async def test_task_removed_from_set_after_completion(self):
        async def noop():
            pass

        task = spawn(noop(), name="noop")
        assert task is not None
        assert task in _background_tasks
        await task
        # After done callback fires, task should be discarded
        assert task not in _background_tasks

    async def test_spawn_without_name(self):
        async def noop():
            pass

        task = spawn(noop())
        assert task is not None
        await task

    async def test_spawn_with_failing_coroutine(self):
        async def failing():
            msg = "boom"
            raise ValueError(msg)

        task = spawn(failing(), name="fail-task")
        assert task is not None
        # Wait for it to finish (it will raise internally)
        await asyncio.sleep(0.01)
        assert task.done()
        # Task should be removed from background set even on failure
        assert task not in _background_tasks

    async def test_multiple_spawns_tracked(self):
        count = 3
        tasks = []

        async def slow():
            await asyncio.sleep(0.05)

        for i in range(count):
            t = spawn(slow(), name=f"task-{i}")
            assert t is not None
            tasks.append(t)

        # All tasks should be tracked
        for t in tasks:
            assert t in _background_tasks

        await asyncio.gather(*tasks)

        # All should be cleaned up
        for t in tasks:
            assert t not in _background_tasks

    def test_spawn_without_event_loop_returns_none(self):
        """When no event loop is running, spawn should close the coro and return None."""
        # This test runs sync (no event loop), so create_task should fail.
        # However, pytest-asyncio auto mode wraps everything... we need to run
        # this in a way that there's no running loop.

        async def coro():
            pass  # pragma: no cover

        c = coro()
        # Simulate no running loop by calling spawn from a thread with no loop
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(spawn, c, name="no-loop")
            result = future.result()
        assert result is None
