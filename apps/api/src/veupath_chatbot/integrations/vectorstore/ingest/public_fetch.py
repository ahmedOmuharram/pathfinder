from __future__ import annotations

import asyncio

import httpx
from veupath_chatbot.integrations.vectorstore.ingest.public_strategies_helpers import (
    backoff_delay_seconds,
)
from veupath_chatbot.platform.types import JSONArray, JSONObject


async def _sleep_backoff(attempt: int) -> None:
    await asyncio.sleep(backoff_delay_seconds(attempt))


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
    last_exc: Exception | None = None
    for attempt in range(1, 6):
        try:
            resp = await client.post(
                "/users/current/strategies",
                json={"sourceStrategySignature": signature},
                timeout=httpx.Timeout(90.0),
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict) or "id" not in data:
                raise RuntimeError("Unexpected duplicateStrategy response")
            return int(data["id"])
        except (
            httpx.ReadTimeout,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ) as exc:
            last_exc = exc
            await _sleep_backoff(attempt)
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            status = exc.response.status_code
            if status in (429, 500, 502, 503, 504):
                await _sleep_backoff(attempt)
            else:
                raise
    raise RuntimeError(f"duplicate_strategy failed after retries: {last_exc!r}")


async def _get_strategy_details(
    client: httpx.AsyncClient, strategy_id: int
) -> JSONObject:
    last_exc: Exception | None = None
    for attempt in range(1, 6):
        try:
            resp = await client.get(
                f"/users/current/strategies/{strategy_id}",
                timeout=httpx.Timeout(180.0),
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise RuntimeError("Unexpected strategy details response")
            return data
        except (
            httpx.ReadTimeout,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ) as exc:
            last_exc = exc
            await _sleep_backoff(attempt)
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            status = exc.response.status_code
            if status in (429, 500, 502, 503, 504):
                await _sleep_backoff(attempt)
            else:
                raise
    raise RuntimeError(f"get_strategy_details failed after retries: {last_exc!r}")


async def _delete_strategy(client: httpx.AsyncClient, strategy_id: int) -> None:
    resp = await client.delete(f"/users/current/strategies/{strategy_id}")
    if resp.status_code >= 400:
        return
