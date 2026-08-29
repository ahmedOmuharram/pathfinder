#!/usr/bin/env python3
"""Sync every embedding index this deployment reads.

Run from the api directory:
    uv run python scripts/sync_embeddings.py

The catalogs sync as they load, and the study index syncs once. An index that
is already level embeds nothing.
"""

import asyncio
import time

from assistant_core.embeddings.embedder import EmbeddingUnavailableError

from pathfinder.integrations.veupathdb.discovery_service import get_discovery_service
from pathfinder.integrations.veupathdb.site_router import get_site_router
from pathfinder.platform.errors import AppError
from pathfinder.services.eda.catalog import preload_study_index


async def main() -> None:
    router = get_site_router()
    sites = router.list_sites()
    discovery = get_discovery_service()

    print(f"Syncing {len(sites)} catalogs...\n")
    for site in sites:
        started = time.time()
        try:
            catalog = await discovery.get_catalog(site.id)
        except (AppError, EmbeddingUnavailableError, OSError, RuntimeError) as exc:
            print(f"  {site.id}: FAILED ({time.time() - started:.1f}s) - {exc}")
        else:
            elapsed = time.time() - started
            print(f"  {site.id}: {elapsed:.1f}s {catalog.index_sync_report}")

    started = time.time()
    report = await preload_study_index()
    print(f"\neda-studies: {time.time() - started:.1f}s {report}")


if __name__ == "__main__":
    asyncio.run(main())
