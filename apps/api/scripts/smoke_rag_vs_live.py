from __future__ import annotations

import argparse
import asyncio

from veupath_chatbot.integrations.veupathdb.factory import get_discovery_service
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.services.embeddings.openai_embeddings import embed_one
from veupath_chatbot.services.vectorstore.collections import EXAMPLE_PLANS_V1, WDK_SEARCHES_V1
from veupath_chatbot.services.vectorstore.qdrant_store import QdrantStore


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="plasmodb")
    parser.add_argument("--query", default="gametocyte")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    s = get_settings()
    if not s.openai_api_key:
        raise SystemExit("openai_api_key is required for embeddings-based smoke test")

    # Live (existing) search_for_searches behavior
    discovery = get_discovery_service()
    live = await discovery.get_record_types(args.site)
    record_types = [
        (rt.get("urlSegment") or rt.get("name") or "")
        for rt in live
        if isinstance(rt, dict)
    ]
    record_types = [rt for rt in record_types if rt]

    # Basic live search: scan searches in each record type and match query in name/display/desc.
    q = args.query.lower()
    live_hits: set[tuple[str, str]] = set()
    for rt in record_types:
        searches = await discovery.get_searches(args.site, rt)
        for se in searches:
            name = (se.get("urlSegment") or se.get("name") or "").lower()
            display = (se.get("displayName") or "").lower()
            desc = (se.get("description") or "").lower()
            if q and (q in name or q in display or q in desc):
                live_hits.add((rt, se.get("urlSegment") or se.get("name") or ""))

    # RAG search from Qdrant
    store = QdrantStore.from_settings()
    vec = await embed_one(text=args.query, model=s.embeddings_model)
    rag_hits = await store.search(
        collection=WDK_SEARCHES_V1,
        query_vector=vec,
        limit=args.limit,
        must=[{"key": "siteId", "value": args.site}],
    )
    rag_pairs = {
        (h["payload"].get("recordType"), h["payload"].get("searchName")) for h in rag_hits
    }

    overlap = {p for p in rag_pairs if p in live_hits}
    print("site:", args.site)
    print("query:", args.query)
    print("live_hits:", len(live_hits))
    print("rag_hits:", len(rag_pairs))
    print("overlap:", len(overlap))
    print("rag_only_sample:", list(sorted(rag_pairs - live_hits))[:5])
    print("live_only_sample:", list(sorted(live_hits - rag_pairs))[:5])

    # Example plans RAG
    example_hits = await store.search(
        collection=EXAMPLE_PLANS_V1,
        query_vector=vec,
        limit=min(args.limit, 5),
        must=[{"key": "siteId", "value": args.site}],
    )
    print("example_plans_hits:", len(example_hits))
    for h in example_hits[:3]:
        p = h.get("payload") or {}
        print(
            " -",
            (p.get("generatedName") or p.get("sourceName") or "")[:80],
            "|",
            (p.get("recordClassName") or "")[:40],
        )


if __name__ == "__main__":
    asyncio.run(main())

