"""What a client that abandons ``search_example_plans`` leaves behind.

The tool embeds every public strategy of a site. A stateless streamable-HTTP
call runs in the session manager's own task group
(``mcp/server/streamable_http_manager.py``, ``_handle_stateless_request``), so
the request ending cancels nothing: the tool asks whether the caller is still
there, at every batch boundary. Two callers on one site must also not embed at
the same time.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator, Sequence
from typing import Any

import pytest

from pathfinder.integrations.veupathdb.wdk_models import WDKStrategySummary
from pathfinder.mcp import server
from pathfinder.mcp.__main__ import build_app
from pathfinder.mcp.metadata import DEFAULT_MCP_PATH
from pathfinder.platform.config import get_settings
from pathfinder.services.catalog.public_strategy_search import EMBED_BATCH

SITE = "plasmodb"


class _FakeStrategyApi:
    def __init__(self, count: int) -> None:
        self._count = count

    async def list_public_strategies(self) -> list[WDKStrategySummary]:
        return [
            WDKStrategySummary(strategy_id=i, name=f"S{i}", root_step_id=i)
            for i in range(self._count)
        ]


@pytest.fixture
def public_strategies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server.wdk, "get_strategy_api", lambda _site: _FakeStrategyApi(EMBED_BATCH * 4)
    )


async def test_an_abandoned_call_stops_embedding(
    public_strategies: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del public_strategies
    entered = asyncio.Event()
    release = asyncio.Event()
    calls: list[int] = []

    async def fake_embed(texts: Sequence[str]) -> list[list[float]]:
        calls.append(len(texts))
        if len(calls) == 2:
            entered.set()
            await release.wait()
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(server, "embed_text", fake_embed)

    task = asyncio.create_task(server.search_example_plans(SITE, "gene expression"))
    await entered.wait()
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)

    assert len(calls) == 2


async def test_two_callers_on_one_site_embed_one_at_a_time(
    public_strategies: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del public_strategies
    inflight = 0
    peak = 0

    async def fake_embed(texts: Sequence[str]) -> list[list[float]]:
        nonlocal inflight, peak
        inflight += 1
        peak = max(peak, inflight)
        await asyncio.sleep(0)
        inflight -= 1
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(server, "embed_text", fake_embed)

    await asyncio.gather(
        server.search_example_plans(SITE, "gene expression"),
        server.search_example_plans(SITE, "gene expression"),
    )

    assert peak == 1


async def test_an_abandoned_call_releases_the_site(
    public_strategies: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The next caller is not blocked by a call whose client walked away."""
    del public_strategies
    entered = asyncio.Event()
    release = asyncio.Event()
    calls: list[int] = []

    async def fake_embed(texts: Sequence[str]) -> list[list[float]]:
        calls.append(len(texts))
        if len(calls) == 1:
            entered.set()
            await release.wait()
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(server, "embed_text", fake_embed)

    abandoned = asyncio.create_task(server.search_example_plans(SITE, "q"))
    await entered.wait()
    abandoned.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await abandoned

    plans = await server.search_example_plans(SITE, "q")

    assert isinstance(plans, list)


SERVICE_SECRET = "wdk-mcp-service-secret-0123456789ab"


@pytest.fixture
def mcp_deployment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("PATHFINDER_MCP_BASE_URL", "https://wdk-mcp.test")
    monkeypatch.setenv("PATHFINDER_MCP_SERVICE_TOKENS", f"gene-page:{SERVICE_SECRET}")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _call_scope(body: bytes) -> dict[str, Any]:
    """The ASGI scope of one credentialed tools/call POST."""
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": DEFAULT_MCP_PATH,
        "raw_path": DEFAULT_MCP_PATH.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"wdk-mcp.test"),
            (b"accept", b"application/json, text/event-stream"),
            (b"content-type", b"application/json"),
            (b"authorization", f"Bearer {SERVICE_SECRET}".encode()),
            (b"content-length", str(len(body)).encode()),
        ],
        "client": ("127.0.0.1", 51234),
        "server": ("wdk-mcp.test", 443),
    }


async def test_a_client_that_drops_the_post_stops_the_served_work(
    mcp_deployment: None,
    public_strategies: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole served stack, driven to the disconnect a dropped POST sends."""
    del mcp_deployment, public_strategies
    entered = asyncio.Event()
    release = asyncio.Event()
    dropped = asyncio.Event()
    calls: list[int] = []

    async def fake_embed(texts: Sequence[str]) -> list[list[float]]:
        calls.append(len(texts))
        if len(calls) == 2:
            entered.set()
            await release.wait()
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(server, "embed_text", fake_embed)

    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search_example_plans",
                "arguments": {"site_id": SITE, "query": "gametocyte genes"},
            },
        }
    ).encode()
    body_sent = False

    async def receive() -> dict[str, Any]:
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await dropped.wait()
        return {"type": "http.disconnect"}

    async def send(_message: dict[str, Any]) -> None:
        return None

    app = build_app()
    async with asyncio.timeout(30), app.router.lifespan_context(app):
        served = asyncio.create_task(app(_call_scope(body), receive, send))
        await entered.wait()
        dropped.set()
        release.set()
        for _ in range(200):
            await asyncio.sleep(0)
        served.cancel()
        await asyncio.gather(served, return_exceptions=True)

    assert calls == [1, EMBED_BATCH]
