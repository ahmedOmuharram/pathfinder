import httpx


async def test_health(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert "version" in body
    assert "timestamp" in body


async def test_ready(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"


async def test_open_strategy_requires_auth(client: httpx.AsyncClient) -> None:
    """Unauthenticated requests to open_strategy should be rejected."""
    resp = await client.post("/api/v1/strategies/open", json={"siteId": "plasmodb"})
    assert resp.status_code == 401
