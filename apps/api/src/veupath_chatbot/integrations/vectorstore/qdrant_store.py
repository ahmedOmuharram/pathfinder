import hashlib
import json
import threading
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from qdrant_client import AsyncQdrantClient

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import InternalError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue


def stable_json_dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def context_hash(context: JSONObject) -> str:
    """Stable hash for (WDK-wire) contextParamValues.

    :param context: Context param dict from WDK wire format.
    :returns: SHA256 hex digest.
    """
    return sha256_hex(stable_json_dumps(context))


_POINT_ID_NAMESPACE = uuid.UUID("2d63b9a8-1c3b-4ab2-8e4a-8b5b0b8c0b6f")


def point_uuid(key: str) -> str:
    """Deterministic UUID for a human-readable key.

    Qdrant point IDs must be either an integer or UUID.

    :param key: Human-readable key.
    :returns: UUID string.
    """
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, key))


@dataclass
class QdrantStore:
    url: str
    api_key: str | None = None
    timeout_seconds: float = 10.0
    _shared_client: AsyncQdrantClient | None = field(
        default=None, init=False, repr=False
    )
    _client_lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False
    )

    @classmethod
    def from_settings(cls) -> QdrantStore:
        s = get_settings()
        api_key = s.qdrant_api_key
        if api_key is not None and not str(api_key).strip():
            api_key = None
        store = cls(
            url=s.qdrant_url,
            api_key=api_key,
            timeout_seconds=float(s.qdrant_timeout_seconds),
        )
        _active_stores.append(store)
        return store

    def _create_client(self) -> AsyncQdrantClient:
        from qdrant_client import AsyncQdrantClient

        return AsyncQdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=int(self.timeout_seconds)
            if self.timeout_seconds is not None
            else None,
        )

    def _get_client(self) -> AsyncQdrantClient:
        if self._shared_client is not None:
            return self._shared_client
        with self._client_lock:
            if self._shared_client is None:
                self._shared_client = self._create_client()
            return self._shared_client

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncQdrantClient]:
        """Yield the shared persistent AsyncQdrantClient.

        The client is created lazily on first use and reused across all
        subsequent calls.  It is NOT closed when the context manager exits;
        call :meth:`close` during application shutdown instead.
        """
        yield self._get_client()

    async def close(self) -> None:
        """Close the shared client and release its connection pool.

        Safe to call multiple times or when no client has been created.
        """
        if self._shared_client is not None:
            await self._shared_client.close()
            self._shared_client = None

    async def reset_collections(self, *names: str) -> None:
        """Delete collections if they exist (used before re-ingestion)."""
        async with self.connect() as client:
            for name in names:
                if await client.collection_exists(collection_name=name):
                    await client.delete_collection(collection_name=name)

    async def ensure_collection(
        self,
        *,
        name: str,
        vector_size: int,
        distance: str = "Cosine",
    ) -> None:
        """Create collection if missing; validate vector size if present."""
        from qdrant_client.models import Distance, VectorParams

        async with self.connect() as client:
            exists = await client.collection_exists(collection_name=name)
            if not exists:
                dist = {
                    "Cosine": Distance.COSINE,
                    "Dot": Distance.DOT,
                    "Euclid": Distance.EUCLID,
                    "Manhattan": Distance.MANHATTAN,
                }.get(distance)
                if dist is None:
                    raise ValueError(f"Unsupported distance: {distance}")
                await client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=vector_size, distance=dist),
                )
                return

            info = await client.get_collection(collection_name=name)
            # Validate vector size to prevent silent corruption.
            # PathFinder uses simple dense vectors, so `vectors` is always VectorParams.
            current = info.config.params.vectors
            if isinstance(current, VectorParams) and current.size is not None:
                size = int(current.size)
                if size != int(vector_size):
                    raise InternalError(
                        title="Vector store misconfigured",
                        detail=f"Qdrant collection {name} has vector size {size}, expected {vector_size}",
                    )

    async def upsert(
        self,
        *,
        collection: str,
        points: JSONArray,
    ) -> None:
        """Upsert points.\n\n        Each point dict: {\"id\": str|int, \"vector\": list[float], \"payload\": dict}\n"""
        from qdrant_client.models import PointStruct

        from veupath_chatbot.platform.types import as_json_object

        q_points: list[PointStruct] = []
        for p_value in points:
            if not isinstance(p_value, dict):
                continue
            p = as_json_object(p_value)
            point_id = p.get("id")
            vector_value = p.get("vector")
            payload_value = p.get("payload")

            if point_id is None or vector_value is None:
                continue

            # Ensure vector is list[float]
            if not isinstance(vector_value, list):
                continue
            vector: list[float] = []
            for v in vector_value:
                if isinstance(v, (int, float)):
                    vector.append(float(v))
                else:
                    break
            else:
                # Only create PointStruct if vector is valid
                payload: JSONObject = {}
                if isinstance(payload_value, dict):
                    payload = {str(k): v for k, v in payload_value.items()}
                q_points.append(
                    PointStruct(
                        id=point_id
                        if isinstance(point_id, (str, int))
                        else str(point_id),
                        vector=vector,
                        payload=payload,
                    )
                )
        if not q_points:
            return
        async with self.connect() as client:
            await client.upsert(collection_name=collection, points=q_points)

    async def get(self, *, collection: str, point_id: str) -> JSONObject | None:
        async with self.connect() as client:
            return await self._get_with_client(client, collection, point_id)

    async def _get_with_client(
        self, client: AsyncQdrantClient, collection: str, point_id: str
    ) -> JSONObject | None:
        try:
            res = await client.retrieve(collection_name=collection, ids=[point_id])
        except Exception as exc:
            # Missing collection, Qdrant down, etc. Treat as cache miss.
            _maybe_log_qdrant_error("get", collection=collection, error=exc)
            return None
        if not res:
            return None
        p = res[0]
        # PathFinder uses simple dense vectors (OpenAI embeddings).
        # p.vector is either None or list[float].
        vector: JSONValue = None
        if isinstance(p.vector, list):
            vector = [float(v) for v in p.vector if isinstance(v, (int, float))]
        return {
            "id": str(p.id),
            "payload": p.payload or {},
            "vector": vector,
        }

    async def search(
        self,
        *,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        must: JSONArray | None = None,
        must_not: JSONArray | None = None,
    ) -> JSONArray:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        from veupath_chatbot.platform.types import as_json_object

        def _cond(item_value: JSONValue) -> FieldCondition:
            if not isinstance(item_value, dict):
                raise ValueError("Filter condition must be a dict")
            item = as_json_object(item_value)
            key = str(item["key"])
            value = item["value"]
            # MatchValue only accepts bool, int, or str
            match_value: bool | int | str
            if isinstance(value, (bool, int, str)):
                match_value = value
            elif isinstance(value, float):
                # MatchValue doesn't accept float, convert non-integers to string
                match_value = int(value) if value.is_integer() else str(value)
            else:
                match_value = str(value)
            return FieldCondition(key=key, match=MatchValue(value=match_value))

        f: Filter | None = None
        if must or must_not:
            from qdrant_client.models import (
                HasIdCondition,
                HasVectorCondition,
                IsEmptyCondition,
                IsNullCondition,
                NestedCondition,
            )

            # Filter expects union types, but FieldCondition is compatible
            # We need to satisfy mypy's type checking by ensuring compatibility
            must_conditions: list[
                FieldCondition
                | IsEmptyCondition
                | IsNullCondition
                | HasIdCondition
                | HasVectorCondition
                | NestedCondition
                | Filter
            ] = []
            if must:
                for m in must:
                    cond = _cond(m)
                    # FieldCondition is compatible with the union type
                    must_conditions.append(cond)
            must_not_conditions: list[
                FieldCondition
                | IsEmptyCondition
                | IsNullCondition
                | HasIdCondition
                | HasVectorCondition
                | NestedCondition
                | Filter
            ] = []
            if must_not:
                for m in must_not:
                    cond = _cond(m)
                    must_not_conditions.append(cond)
            f = Filter(
                must=must_conditions if must_conditions else None,
                must_not=must_not_conditions if must_not_conditions else None,
            )

        async with self.connect() as client:
            # qdrant-client async API uses `query_points` (not `search`) in newer versions.
            try:
                hits = await client.query_points(
                    collection_name=collection,
                    query=query_vector,
                    query_filter=f,
                    limit=max(int(limit), 1),
                    with_payload=True,
                )
            except Exception as exc:
                # Most common: 404 missing collection when ingestion hasn't run yet.
                _maybe_log_qdrant_error("search", collection=collection, error=exc)
                return []
            points = hits.points or []
            return [
                {
                    "id": str(p.id),
                    "score": float(p.score) if p.score is not None else 0.0,
                    "payload": p.payload or {},
                }
                for p in points
            ]


_active_stores: list[QdrantStore] = []


async def close_all_qdrant_stores() -> None:
    """Close every QdrantStore created via ``from_settings()``.

    Called during application shutdown to release all Qdrant connection pools.
    """
    for store in list(_active_stores):
        await store.close()
    _active_stores.clear()


def _maybe_log_qdrant_error(op: str, *, collection: str, error: Exception) -> None:
    """Log Qdrant errors without spamming in normal flows.

    :param op: Operation name (e.g. "upsert", "search").
    :param collection: Collection name.
    :param error: Exception that occurred.
    """
    try:
        from qdrant_client.http.exceptions import UnexpectedResponse

        # Missing collection is an expected state pre-ingestion.
        if (
            isinstance(error, UnexpectedResponse)
            and int(getattr(error, "status_code", 0) or 0) == 404
        ):
            return
    except Exception:
        # If qdrant-client internals changed, fall back to string check below.
        pass
    msg = str(error)
    if "doesn't exist" in msg or "Not found: Collection" in msg:
        return
    get_logger(__name__).warning(
        "Qdrant operation failed",
        op=op,
        collection=collection,
        error=msg,
        errorType=type(error).__name__,
    )
