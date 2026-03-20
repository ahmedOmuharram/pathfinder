import asyncio

import pytest

from veupath_chatbot.integrations.vectorstore.ingest.pipeline import (
    run_concurrent_pipeline,
)


@pytest.mark.asyncio
async def test_basic_pipeline_processes_all_items():
    """All items are processed and flushed."""
    processed: list[int] = []
    flushed: list[list[int]] = []

    async def process(item: int) -> int:
        return item * 2

    async def flush(batch: list[int]) -> None:
        flushed.append(list(batch))
        processed.extend(batch)

    await run_concurrent_pipeline(
        items=[1, 2, 3, 4, 5],
        process_fn=process,
        flush_fn=flush,
        concurrency=2,
        batch_size=3,
    )

    assert sorted(processed) == [2, 4, 6, 8, 10]
    # With batch_size=3, we expect at least 2 flush calls (3 + 2)
    total_flushed = sum(len(b) for b in flushed)
    assert total_flushed == 5


@pytest.mark.asyncio
async def test_pipeline_respects_batch_size():
    """Batches are flushed when they reach batch_size."""
    flushed_sizes: list[int] = []

    async def process(item: int) -> int:
        return item

    async def flush(batch: list[int]) -> None:
        flushed_sizes.append(len(batch))

    await run_concurrent_pipeline(
        items=list(range(10)),
        process_fn=process,
        flush_fn=flush,
        concurrency=1,
        batch_size=4,
    )

    # 10 items with batch_size=4: batches of [4, 4, 2]
    assert flushed_sizes == [4, 4, 2]


@pytest.mark.asyncio
async def test_pipeline_handles_empty_items():
    """Empty input produces no flush calls."""
    flushed: list[list[int]] = []

    async def process(item: int) -> int:
        return item

    async def flush(batch: list[int]) -> None:
        flushed.append(list(batch))

    await run_concurrent_pipeline(
        items=[],
        process_fn=process,
        flush_fn=flush,
        concurrency=2,
        batch_size=5,
    )

    assert flushed == []


@pytest.mark.asyncio
async def test_pipeline_process_fn_returns_none_skips():
    """When process_fn returns None, the item is not flushed."""
    flushed: list[list[int]] = []

    async def process(item: int) -> int | None:
        if item % 2 == 0:
            return None
        return item

    async def flush(batch: list[int]) -> None:
        flushed.append(list(batch))

    await run_concurrent_pipeline(
        items=[1, 2, 3, 4, 5],
        process_fn=process,
        flush_fn=flush,
        concurrency=2,
        batch_size=10,
    )

    total = [x for batch in flushed for x in batch]
    assert sorted(total) == [1, 3, 5]


@pytest.mark.asyncio
async def test_pipeline_concurrency_respected():
    """Verify concurrent workers don't exceed concurrency limit."""
    active = 0
    max_active = 0

    async def process(item: int) -> int:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return item

    async def flush(batch: list[int]) -> None:
        pass

    await run_concurrent_pipeline(
        items=list(range(20)),
        process_fn=process,
        flush_fn=flush,
        concurrency=3,
        batch_size=100,
    )

    assert max_active <= 3


@pytest.mark.asyncio
async def test_pipeline_on_error_callback():
    """on_error callback is called for items that raise exceptions."""
    errors: list[tuple[int, Exception]] = []

    async def process(item: int) -> int:
        if item == 3:
            msg = "bad item"
            raise ValueError(msg)
        return item

    def on_error(item: int, exc: Exception) -> None:
        errors.append((item, exc))

    flushed: list[list[int]] = []

    async def flush(batch: list[int]) -> None:
        flushed.append(list(batch))

    await run_concurrent_pipeline(
        items=[1, 2, 3, 4, 5],
        process_fn=process,
        flush_fn=flush,
        concurrency=2,
        batch_size=10,
        on_error=on_error,
    )

    assert len(errors) == 1
    assert errors[0][0] == 3
    assert isinstance(errors[0][1], ValueError)

    total = [x for batch in flushed for x in batch]
    assert sorted(total) == [1, 2, 4, 5]


@pytest.mark.asyncio
async def test_pipeline_error_without_callback_is_silent():
    """Without on_error, exceptions in process_fn are silently swallowed."""
    flushed: list[list[int]] = []

    async def process(item: int) -> int:
        if item == 2:
            msg = "boom"
            raise RuntimeError(msg)
        return item

    async def flush(batch: list[int]) -> None:
        flushed.append(list(batch))

    await run_concurrent_pipeline(
        items=[1, 2, 3],
        process_fn=process,
        flush_fn=flush,
        concurrency=1,
        batch_size=10,
    )

    total = [x for batch in flushed for x in batch]
    assert sorted(total) == [1, 3]


@pytest.mark.asyncio
async def test_pipeline_single_item():
    """Pipeline works with just one item."""
    flushed: list[list[str]] = []

    async def process(item: str) -> str:
        return item.upper()

    async def flush(batch: list[str]) -> None:
        flushed.append(list(batch))

    await run_concurrent_pipeline(
        items=["hello"],
        process_fn=process,
        flush_fn=flush,
        concurrency=1,
        batch_size=10,
    )

    assert flushed == [["HELLO"]]


@pytest.mark.asyncio
async def test_pipeline_batch_size_one():
    """batch_size=1 flushes after every item."""
    flushed_sizes: list[int] = []

    async def process(item: int) -> int:
        return item

    async def flush(batch: list[int]) -> None:
        flushed_sizes.append(len(batch))

    await run_concurrent_pipeline(
        items=[1, 2, 3],
        process_fn=process,
        flush_fn=flush,
        concurrency=1,
        batch_size=1,
    )

    assert flushed_sizes == [1, 1, 1]
