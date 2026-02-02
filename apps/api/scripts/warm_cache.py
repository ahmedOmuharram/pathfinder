#!/usr/bin/env python3
"""Pre-fetch and cache VEuPathDB metadata."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from veupath_chatbot.veupathdb.discovery import get_discovery_service
from veupath_chatbot.veupathdb.site_router import get_site_router


async def main():
    """Warm up the cache by loading all site metadata."""
    print("Warming up VEuPathDB metadata cache...")

    router = get_site_router()
    discovery = get_discovery_service()

    sites = router.list_sites()
    print(f"Found {len(sites)} sites to cache")

    for site in sites:
        print(f"  Loading {site.display_name}...")
        try:
            catalog = await discovery.get_catalog(site.id)
            record_types = catalog.get_record_types()
            total_searches = sum(
                len(catalog.get_searches(rt.get("urlSegment", "")))
                for rt in record_types
            )
            print(f"    -> {len(record_types)} record types, {total_searches} searches")
        except Exception as e:
            print(f"    -> Error: {e}")

    print("\nCache warming complete!")

    # Clean up
    await router.close_all()


if __name__ == "__main__":
    asyncio.run(main())

