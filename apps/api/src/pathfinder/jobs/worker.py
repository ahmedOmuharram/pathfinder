"""Entry point for the Pathfinder Procrastinate worker.

Run with ``python -m pathfinder.jobs.worker``. ``register_all_tools`` imports
``tasks`` (so ``@procrastinate_app.task`` decorators register the task
names) and populates ``TOOL_REGISTRY`` before ``run_worker_async`` starts
pulling jobs.
"""

from __future__ import annotations

import asyncio
import logging

from assistant_core.mcp.admission import install_admitted_sources
from assistant_core.platform.logging import setup_logging

from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.impls import register_all_tools
from pathfinder.jobs.logging_filters import install_procrastinate_redaction
from pathfinder.platform.config import get_settings
from pathfinder.platform.tool_sources import admitted_tool_sources


async def amain() -> None:
    setup_logging()
    install_procrastinate_redaction()
    logging.getLogger(__name__).info("Pathfinder worker starting")
    # Turns run here, so this is the process where a declaration resolves.
    install_admitted_sources(admitted_tool_sources())
    register_all_tools()
    async with procrastinate_app.open_async():
        await procrastinate_app.run_worker_async(
            queues=["chat_turn", "default", "maintenance", "verification"],
            concurrency=get_settings().worker_concurrency,
            install_signal_handlers=True,
        )


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
