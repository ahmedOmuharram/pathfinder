import asyncio
from collections.abc import Awaitable, Callable

import httpx

from veupath_chatbot.integrations.vectorstore.ingest.public_strategies_helpers import (
    backoff_delay_seconds,
)
from veupath_chatbot.platform.types import JSONArray, JSONObject

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_HTTP_BAD_REQUEST = 400


async def _sleep_backoff(attempt: int) -> None:
    await asyncio.sleep(backoff_delay_seconds(attempt))


async def _retry_request[T](
    action: Callable[[], Awaitable[T]],
    label: str,
    max_attempts: int = 5,
) -> T:
    """Execute *action* with retry on transient HTTP failures."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await action()
        except (
            httpx.ReadTimeout,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ) as exc:
            last_exc = exc
            await _sleep_backoff(attempt)
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code in _RETRYABLE_STATUS_CODES:
                await _sleep_backoff(attempt)
            else:
                raise
    msg = f"{label} failed after retries: {last_exc!r}"
    raise RuntimeError(msg)


async def _fetch_public_strategy_summaries(
    client: httpx.AsyncClient,
) -> JSONArray:
    resp = await client.get("/strategy-lists/public")
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


async def _duplicate_strategy(client: httpx.AsyncClient, signature: str) -> int:
    async def _do() -> int:
        resp = await client.post(
            "/users/current/strategies",
            json={"sourceStrategySignature": signature},
            timeout=httpx.Timeout(90.0),
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict) or "id" not in data:
            msg = "Unexpected duplicateStrategy response"
            raise RuntimeError(msg)
        return int(data["id"])

    return await _retry_request(_do, "duplicate_strategy")


async def _get_strategy_details(
    client: httpx.AsyncClient, strategy_id: int
) -> JSONObject:
    async def _do() -> JSONObject:
        resp = await client.get(
            f"/users/current/strategies/{strategy_id}",
            timeout=httpx.Timeout(180.0),
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            msg = "Unexpected strategy details response"
            raise TypeError(msg)
        return data

    return await _retry_request(_do, "get_strategy_details")


async def _delete_strategy(client: httpx.AsyncClient, strategy_id: int) -> None:
    resp = await client.delete(f"/users/current/strategies/{strategy_id}")
    if resp.status_code >= _HTTP_BAD_REQUEST:
        return
