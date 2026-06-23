from __future__ import annotations

import asyncio

from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.ai.memory.reembed import reembed_all_memories
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.platform.config import get_settings


async def _run() -> int:
    settings = get_settings()
    async with lifespan_memory_store(settings.database_url) as raw_store:
        return await reembed_all_memories(MemoryStore(store=raw_store))


def main() -> int:
    count = asyncio.run(_run())
    print(f"re-embedded {count} memories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
