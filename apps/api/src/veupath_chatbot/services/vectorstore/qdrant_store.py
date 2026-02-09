from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

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
    def from_settings(cls) -> QdrantStore:
        s = get_settings()
        api_key = s.qdrant_api_key
        if api_key is not None and not str(api_key).strip():
            api_key = None
        return cls(
            url=s.qdrant_url,
            api_key=api_key,
            timeout_seconds=float(s.qdrant_timeout_seconds),
        )

    def _client(self) -> AsyncQdrantClient:
        from qdrant_client import AsyncQdrantClient

        return AsyncQdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=int(self.timeout_seconds)
            if self.timeout_seconds is not None
            else None,
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
        current = info.config.params.vectors
        # `current` can be either VectorParams or a dict of named vectors.
        if current is not None:
            if hasattr(current, "size"):
                size = int(current.size)
                if size != int(vector_size):
                    raise InternalError(
                        title="Vector store misconfigured",
                        detail=f"Qdrant collection {name} has vector size {size}, expected {vector_size}",
                    )
            elif isinstance(current, dict) and current:
                any_vec = next(iter(current.values()))
                if hasattr(any_vec, "size"):
                    size = int(any_vec.size)
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

        client = self._client()
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
                payload: dict[str, object] = {}
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
        await client.upsert(collection_name=collection, points=q_points)

    async def get(self, *, collection: str, point_id: str) -> JSONObject | None:
        client = self._client()
        try:
            res = await client.retrieve(collection_name=collection, ids=[point_id])
        except Exception as exc:
            # Missing collection, Qdrant down, etc. Treat as cache miss.
            _maybe_log_qdrant_error("get", collection=collection, error=exc)
            return None
        if not res:
            return None
        p = res[0]
        # Convert vector to JSON-compatible format
        vector_value: JSONValue
        if p.vector is None:
            vector_value = None
        elif isinstance(p.vector, list):
            # Convert to list[float] then to JSONValue (list[JsonValue])
            vector_list: list[JSONValue] = []
            for v in p.vector:
                if isinstance(v, (int, float)):
                    vector_list.append(float(v))
                elif isinstance(v, list):
                    # Nested list (multi-vector)
                    nested: list[JSONValue] = [
                        float(x) if isinstance(x, (int, float)) else x for x in v
                    ]
                    vector_list.append(nested)
                else:
                    # Keep as-is for other types
                    vector_list.append(v)
            vector_value = vector_list
        elif isinstance(p.vector, dict):
            # Handle named vectors or sparse vectors - convert to dict[str, JSONValue]
            vector_dict: dict[str, JSONValue] = {}
            for k, vec_val in p.vector.items():
                key_str = str(k)
                if isinstance(vec_val, list):
                    # Handle list[float] or list[list[float]]
                    if vec_val and isinstance(vec_val[0], list):
                        # Nested list
                        nested_list: list[JSONValue] = []
                        for nested_item in vec_val:
                            if isinstance(nested_item, list):
                                # Convert nested list to list[JSONValue]
                                nested_float_list: list[JSONValue] = []
                                for x in nested_item:
                                    if isinstance(x, (int, float)):
                                        nested_float_list.append(float(x))
                                    else:
                                        nested_float_list.append(x)
                                nested_list.append(nested_float_list)
                            else:
                                nested_list.append(
                                    float(nested_item)
                                    if isinstance(nested_item, (int, float))
                                    else nested_item
                                )
                        vector_dict[key_str] = nested_list
                    else:
                        # Simple list[float] - convert to list[JSONValue]
                        # In this branch, vec_val[0] is not a list, so elements should be scalars
                        float_list: list[JSONValue] = []
                        for item in vec_val:
                            # Handle each item - could be scalar or unexpected nested list
                            if isinstance(item, list):
                                # Unexpected nested list - convert recursively
                                nested_converted: list[JSONValue] = []
                                for sub_item in item:
                                    if isinstance(sub_item, (int, float)):
                                        nested_converted.append(float(sub_item))
                                    else:
                                        nested_converted.append(sub_item)
                                float_list.append(nested_converted)
                            elif isinstance(item, (int, float)):
                                float_list.append(float(item))
                            else:
                                float_list.append(item)
                        vector_dict[key_str] = float_list
                elif isinstance(vec_val, (int, float)):
                    vector_dict[key_str] = float(vec_val)
                else:
                    # Handle SparseVector or other types - convert to dict representation
                    if hasattr(vec_val, "__dict__"):
                        vector_dict[key_str] = {
                            str(attr_k): attr_v
                            for attr_k, attr_v in vec_val.__dict__.items()
                        }
                    else:
                        vector_dict[key_str] = str(vec_val)
            vector_value = vector_dict
        else:
            # Fallback: convert to string representation
            vector_value = str(p.vector)
        return {
            "id": str(p.id),
            "payload": p.payload or {},
            "vector": vector_value,
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

        client = self._client()
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


def _maybe_log_qdrant_error(op: str, *, collection: str, error: Exception) -> None:
    """Log Qdrant errors without spamming in normal flows."""
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
