from __future__ import annotations

import time
from typing import Any

from veupath_chatbot.integrations.veupathdb.client import encode_context_param_values_for_wdk
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.embeddings.openai_embeddings import embed_one
from veupath_chatbot.services.vectorstore.collections import WDK_DEPENDENT_VOCAB_CACHE_V1
from veupath_chatbot.services.vectorstore.qdrant_store import QdrantStore, context_hash, point_uuid


async def ensure_dependent_vocab_collection(store: QdrantStore) -> None:
    """Create the dependent vocab cache collection if missing.

    This collection is used for keyed lookup (site/rt/search/param/contextHash). We still
    store vectors to keep Qdrant schema consistent and allow optional similarity later.
    """
    s = get_settings()
    dim = len(await embed_one(text="dependent-vocab-cache", model=s.embeddings_model))
    await store.ensure_collection(name=WDK_DEPENDENT_VOCAB_CACHE_V1, vector_size=dim)


async def get_dependent_vocab_authoritative_cached(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    param_name: str,
    context_values: dict[str, Any],
    store: QdrantStore | None = None,
) -> dict[str, Any]:
    """Return authoritative dependent vocab, cached in Qdrant.

    - Cache key is the *WDK-wire* encoded context values (json-string encoding for lists/dicts).
    - On cache miss, calls WDK `/refreshed-dependent-params` (via existing client) and stores result.
    """
    store = store or QdrantStore.from_settings()
    await ensure_dependent_vocab_collection(store)

    wdk_context = encode_context_param_values_for_wdk(context_values or {})
    ch = context_hash(wdk_context)
    key = f"{site_id}:{record_type}:{search_name}:{param_name}:{ch}"
    pid = point_uuid(key)

    cached = await store.get(collection=WDK_DEPENDENT_VOCAB_CACHE_V1, point_id=pid)
    if cached and isinstance(cached.get("payload"), dict):
        return {"cache": "hit", **cached["payload"]}

    client = get_wdk_client(site_id)
    try:
        response = await client.get_refreshed_dependent_params(
            record_type, search_name, param_name, wdk_context
        )
    except WDKError as exc:
        if site_id != "veupathdb":
            portal_client = get_wdk_client("veupathdb")
            response = await portal_client.get_refreshed_dependent_params(
                record_type, search_name, param_name, wdk_context
            )
        else:
            raise exc

    payload: dict[str, Any] = {
        "siteId": site_id,
        "recordType": record_type,
        "searchName": search_name,
        "paramName": param_name,
        "contextParamValues": wdk_context,
        "contextHash": ch,
        "wdkResponse": response,
        "ingestedAt": int(time.time()),
        "sourceUrl": f"{client.base_url}/record-types/{record_type}/searches/{search_name}/refreshed-dependent-params",
    }

    # Minimal vector (not used for correctness; just to satisfy collection vector config)
    vec = await embed_one(
        text=f"{site_id} {record_type} {search_name} {param_name}",
        model=get_settings().embeddings_model,
    )
    await store.upsert(
        collection=WDK_DEPENDENT_VOCAB_CACHE_V1,
        points=[{"id": pid, "vector": vec, "payload": payload}],
    )
    return {"cache": "miss", **payload}

