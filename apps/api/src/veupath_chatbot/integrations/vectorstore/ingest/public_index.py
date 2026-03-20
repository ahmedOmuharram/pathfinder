from veupath_chatbot.integrations.embeddings.openai_embeddings import OpenAIEmbeddings
from veupath_chatbot.integrations.vectorstore.collections import EXAMPLE_PLANS_V1
from veupath_chatbot.integrations.vectorstore.ingest.public_strategies_helpers import (
    EMBED_TEXT_MAX_CHARS,
    truncate,
)
from veupath_chatbot.integrations.vectorstore.ingest.utils import embed_and_upsert
from veupath_chatbot.integrations.vectorstore.qdrant_store import QdrantStore
from veupath_chatbot.platform.types import JSONArray, JSONObject


async def _flush_batch(
    *,
    store: QdrantStore,
    embedder: OpenAIEmbeddings,
    points: JSONArray,
    texts: list[str],
) -> None:
    """Embed *texts*, pair with *points* metadata, and upsert to the example plans collection.

    Truncates texts to ``EMBED_TEXT_MAX_CHARS`` before embedding, with a
    per-item fallback when the batch embed call fails (e.g. a single
    oversized text causes the whole batch to be rejected by the API).
    """
    if not points:
        return

    ids: list[str] = []
    payloads: list[JSONObject] = []
    for p in points:
        if not isinstance(p, dict):
            continue
        ids.append(str(p.get("id") or ""))
        payload_raw = p.get("payload")
        payloads.append(payload_raw if isinstance(payload_raw, dict) else {})

    safe_texts = [truncate(t, max_chars=EMBED_TEXT_MAX_CHARS) for t in texts]

    try:
        await embed_and_upsert(
            store=store,
            embedder=embedder,
            collection=EXAMPLE_PLANS_V1,
            ids=ids,
            texts=safe_texts,
            payloads=payloads,
        )
    except OSError, RuntimeError, ValueError:
        # Per-item fallback: embed one at a time with aggressive truncation
        # so a single oversized text doesn't block the entire batch.
        for point_id, text, payload in zip(ids, safe_texts, payloads, strict=True):
            fallback_text = truncate(text, max_chars=10_000)
            await embed_and_upsert(
                store=store,
                embedder=embedder,
                collection=EXAMPLE_PLANS_V1,
                ids=[point_id],
                texts=[fallback_text],
                payloads=[payload],
            )
