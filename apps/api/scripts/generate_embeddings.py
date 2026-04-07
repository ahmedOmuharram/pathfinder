#!/usr/bin/env python3
"""Generate pre-computed embedding caches for all VEuPathDB sites.

Run from the api directory:
    uv run python scripts/generate_embeddings.py

Outputs .npz files to src/veupath_chatbot/data/embeddings/ which should
be committed to the repo.  On startup, the API loads these instead of
re-encoding — making catalog warm-up instant.
"""

import asyncio
import time

from veupath_chatbot.integrations.veupathdb.discovery_service import get_discovery_service
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.services.catalog.semantic_index import warm_up_model


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
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  {site.id}: FAILED ({elapsed:.1f}s) - {e}")

    print("\nDone. Commit the .npz files in src/veupath_chatbot/data/embeddings/")


if __name__ == "__main__":
    asyncio.run(main())
