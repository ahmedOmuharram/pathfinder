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


async def test_open_strategy_sets_auth_cookie(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/strategies/open", json={"siteId": "plasmodb"})
    assert resp.status_code == 200
    # Cookie is the public contract.
    set_cookie = resp.headers.get("set-cookie", "")
    assert "pathfinder-auth=" in set_cookie
