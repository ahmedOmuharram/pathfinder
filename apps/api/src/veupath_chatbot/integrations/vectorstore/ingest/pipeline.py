"""Generic concurrent pipeline utility for ingest workers.

Provides a reusable asyncio-based producer/worker/consumer pattern with:
- A pool of concurrent workers that process items via ``process_fn``
- A single consumer that batches results and flushes via ``flush_fn``
- Sentinel-based shutdown with proper queue joining
"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence


async def _run_worker[InT, OutT](
    jobs: asyncio.Queue[InT | None],
    results: asyncio.Queue[OutT | None],
    process_fn: Callable[[InT], Awaitable[OutT | None]],
    on_error: Callable[[InT, Exception], None] | None,
) -> None:
    """Process items from the jobs queue and push results."""
    while True:
        item = await jobs.get()
        if item is None:
            jobs.task_done()
            break
        try:
            result = await process_fn(item)
            if result is not None:
                await results.put(result)
        except (
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            LookupError,
        ) as exc:
            if on_error is not None:
                on_error(item, exc)
        finally:
            jobs.task_done()


async def _run_consumer[OutT](
    results: asyncio.Queue[OutT | None],
    flush_fn: Callable[[list[OutT]], Awaitable[None]],
    batch_size: int,
) -> None:
    """Consume results, batch them, and flush."""
    buffered: list[OutT] = []
    while True:
        item = await results.get()
        if item is None:
            results.task_done()
            break
        buffered.append(item)
        results.task_done()
        if len(buffered) >= batch_size:
            await flush_fn(buffered)
            buffered = []

    if buffered:
        await flush_fn(buffered)


async def run_concurrent_pipeline[InT, OutT](
    *,
    items: Sequence[InT],
    process_fn: Callable[[InT], Awaitable[OutT | None]],
    flush_fn: Callable[[list[OutT]], Awaitable[None]],
    concurrency: int,
    batch_size: int,
    on_error: Callable[[InT, Exception], None] | None = None,
) -> None:
    """Run *items* through a concurrent worker pool, batching results to *flush_fn*.

    Parameters
    ----------
    items:
        The input items to process.
    process_fn:
        Async callable that transforms a single input item into an output.
        Return ``None`` to skip the item (it will not be flushed).
    flush_fn:
        Async callable that receives a batch of outputs to persist/upsert.
    concurrency:
        Maximum number of concurrent worker tasks.
    batch_size:
        Number of outputs to accumulate before calling *flush_fn*.
    on_error:
        Optional sync callback invoked when *process_fn* raises.  If not
        provided, errors are silently swallowed and the item is skipped.
    """
    if not items:
        return

    conc = max(1, int(concurrency))
    bs = max(1, int(batch_size))

    jobs: asyncio.Queue[InT | None] = asyncio.Queue()
    results: asyncio.Queue[OutT | None] = asyncio.Queue()

    workers = [
        asyncio.create_task(_run_worker(jobs, results, process_fn, on_error))
        for _ in range(conc)
    ]
    consumer_task = asyncio.create_task(_run_consumer(results, flush_fn, bs))

    for item in items:
        await jobs.put(item)
    for _ in workers:
        await jobs.put(None)

    await jobs.join()
    await results.put(None)
    await consumer_task
    for w in workers:
        await w
