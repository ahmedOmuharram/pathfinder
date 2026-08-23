#!/usr/bin/env python3
"""Generate pre-computed embedding caches for all VEuPathDB sites.

Run from the api directory:
    uv run python scripts/generate_embeddings.py

Outputs .npz files to src/pathfinder/data/embeddings/ which should
be committed to the repo.  On startup, the API loads these instead of
re-encoding — making catalog warm-up instant.
"""

import asyncio
import time

from assistant_core.embeddings.model import warm_up_model

from pathfinder.integrations.veupathdb.discovery_service import get_discovery_service
from pathfinder.integrations.veupathdb.site_router import get_site_router
from pathfinder.platform.errors import AppError


async def main() -> None:
    print("Loading embedding model...")
    warm_up_model()

    router = get_site_router()
    sites = router.list_sites()
    discovery = get_discovery_service()

    print(f"Generating embeddings for {len(sites)} sites...\n")

    for site in sites:
        t0 = time.time()
        try:
            await discovery.get_catalog(site.id)
            elapsed = time.time() - t0
            print(f"  {site.id}: {elapsed:.1f}s")
        except (AppError, OSError, RuntimeError, ValueError) as e:
            elapsed = time.time() - t0
            print(f"  {site.id}: FAILED ({elapsed:.1f}s) - {e}")

    print("\nDone. Commit the .npz files in src/pathfinder/data/embeddings/")


if __name__ == "__main__":
    asyncio.run(main())
