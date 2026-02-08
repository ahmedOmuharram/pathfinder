from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from veupath_chatbot.platform.config import get_settings


def stable_json_dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def context_hash(context: dict[str, Any]) -> str:
    """Stable hash for (WDK-wire) contextParamValues."""
    return sha256_hex(stable_json_dumps(context))


_POINT_ID_NAMESPACE = uuid.UUID("2d63b9a8-1c3b-4ab2-8e4a-8b5b0b8c0b6f")


def point_uuid(key: str) -> str:
    """Deterministic UUID for a human-readable key.

    Qdrant point IDs must be either an integer or UUID.
    """
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, key))


@dataclass(frozen=True)
class QdrantStore:
    url: str
    api_key: str | None = None
    timeout_seconds: float = 10.0

    @classmethod
    def from_settings(cls) -> "QdrantStore":
        s = get_settings()
        api_key = s.qdrant_api_key
        if api_key is not None and not str(api_key).strip():
            api_key = None
        return cls(
            url=s.qdrant_url,
            api_key=api_key,
            timeout_seconds=float(s.qdrant_timeout_seconds),
        )

    def _client(self):
        from qdrant_client import AsyncQdrantClient

        return AsyncQdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=self.timeout_seconds,
        )

    async def ensure_collection(
        self,
        *,
        name: str,
        vector_size: int,
        distance: str = "Cosine",
    ) -> None:
        """Create collection if missing; validate vector size if present."""
        from qdrant_client.models import Distance, VectorParams

        client = self._client()
        exists = await client.collection_exists(collection_name=name)
        if not exists:
            dist = {
                "Cosine": Distance.COSINE,
                "Dot": Distance.DOT,
                "Euclid": Distance.EUCLID,
                "Manhattan": Distance.MANHATTAN,
            }.get(distance, None)
            if dist is None:
                raise ValueError(f"Unsupported distance: {distance}")
            await client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=vector_size, distance=dist),
            )
            return

        info = await client.get_collection(collection_name=name)
        # Validate vector size to prevent silent corruption.
        current = info.config.params.vectors
        # `current` can be either VectorParams or a dict of named vectors.
        if hasattr(current, "size"):
            size = int(getattr(current, "size"))
            if size != int(vector_size):
                raise RuntimeError(
                    f"Qdrant collection {name} has vector size {size}, expected {vector_size}"
                )
        elif isinstance(current, dict) and current:
            any_vec = next(iter(current.values()))
            if hasattr(any_vec, "size"):
                size = int(getattr(any_vec, "size"))
                if size != int(vector_size):
                    raise RuntimeError(
                        f"Qdrant collection {name} has vector size {size}, expected {vector_size}"
                    )

    async def upsert(
        self,
        *,
        collection: str,
        points: list[dict[str, Any]],
    ) -> None:
        """Upsert points.\n\n        Each point dict: {\"id\": str|int, \"vector\": list[float], \"payload\": dict}\n        """
        from qdrant_client.models import PointStruct

        client = self._client()
        q_points = [
            PointStruct(id=p["id"], vector=p["vector"], payload=p.get("payload") or {})
            for p in points
        ]
        if not q_points:
            return
        await client.upsert(collection_name=collection, points=q_points)

    async def get(self, *, collection: str, point_id: str) -> dict[str, Any] | None:
        client = self._client()
        res = await client.retrieve(collection_name=collection, ids=[point_id])
        if not res:
            return None
        p = res[0]
        return {
            "id": str(p.id),
            "payload": p.payload or {},
            "vector": p.vector,
        }

    async def search(
        self,
        *,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        must: list[dict[str, Any]] | None = None,
        must_not: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        def _cond(item: dict[str, Any]) -> FieldCondition:
            key = str(item["key"])
            value = item["value"]
            return FieldCondition(key=key, match=MatchValue(value=value))

        f = None
        if must or must_not:
            f = Filter(
                must=[_cond(m) for m in (must or [])],
                must_not=[_cond(m) for m in (must_not or [])],
            )

        client = self._client()
        # qdrant-client async API uses `query_points` (not `search`) in newer versions.
        hits = await client.query_points(
            collection_name=collection,
            query=query_vector,
            query_filter=f,
            limit=max(int(limit), 1),
            with_payload=True,
        )
        points = hits.points or []
        return [
            {
                "id": str(p.id),
                "score": float(p.score) if p.score is not None else 0.0,
                "payload": p.payload or {},
            }
            for p in points
        ]

