import httpx
import respx


async def test_list_wdk_strategies_mocked(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    base = "https://plasmodb.org/plasmo/service"

    # WDK UserFormatter emits user ID under "id"; StrategyAPI uses it for /users/{id}/strategies
    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.get(f"{base}/users/guest/strategies").respond(
        200,
        json=[
            {
                "strategyId": 123,
                "name": "My WDK Strategy",
                "rootStepId": 100,
                "isSaved": True,
            }
        ],
    )

    resp = await authed_client.get(
        "/api/v1/strategies/wdk", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["wdkStrategyId"] == 123
    assert body[0]["siteId"] == "plasmodb"
    assert body[0]["name"] == "My WDK Strategy"


async def test_open_strategy_requires_site_id_when_creating_new(
    authed_client: httpx.AsyncClient,
) -> None:
    # When neither strategyId nor wdkStrategyId is provided, siteId is required.
    resp = await authed_client.post("/api/v1/strategies/open", json={})
    assert resp.status_code == 422
