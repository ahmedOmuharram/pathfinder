"""Entry point for the Pathfinder Procrastinate worker.

Run with ``python -m pathfinder.jobs.worker``. ``register_all_tools`` imports
``tasks`` (so ``@procrastinate_app.task`` decorators register the task
names) and populates ``TOOL_REGISTRY`` before ``run_worker_async`` starts
pulling jobs.
"""

from __future__ import annotations

import asyncio
import logging

from pathfinder.ai.memory.embedding import embed_text
from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.impls import register_all_tools
from pathfinder.jobs.logging_filters import install_procrastinate_redaction
from pathfinder.platform.logging import setup_logging


async def _warm_up() -> None:
    """Preload heavy resources so the first durable task doesn't pay cold-start.

    fastembed lazy-loads the embedding model (~2-5s on first use). Without
    this, the first durable task that touches memory indexing stalls —
    which is exactly the path a ``run_durable_task`` run hits right before
    resuming the graph. We pay the cost once at worker start instead.
    """
    logger = logging.getLogger(__name__)
    logger.info("worker warming fastembed model")
    await embed_text(["warm-up"])
    logger.info("worker warm-up complete")


async def amain() -> None:
    setup_logging()
    install_procrastinate_redaction()
    logging.getLogger(__name__).info("Pathfinder worker starting")
    register_all_tools()
    await _warm_up()
    async with procrastinate_app.open_async():
        await procrastinate_app.run_worker_async(
            queues=["chat_turn", "default", "maintenance", "verification"],
            install_signal_handlers=True,
        )


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
