import httpx

from veupath_chatbot.platform.types import JSONObject


def _minimal_plan() -> JSONObject:
    return {
        "recordType": "gene",
        "root": {
            "searchName": "GenesByTextSearch",
            "parameters": {"text": "kinase"},
        },
        "metadata": {"name": "Test Plan"},
    }


async def test_strategy_crud(authed_client: httpx.AsyncClient) -> None:
    # Create
    resp = await authed_client.post(
        "/api/v1/strategies",
        json={"name": "My Strategy", "siteId": "plasmodb", "plan": _minimal_plan()},
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["name"] == "My Strategy"
    assert created["siteId"] == "plasmodb"
    assert created["recordType"] == "gene"
    assert created["rootStepId"]
    assert isinstance(created["steps"], list)
    strategy_id = created["id"]

    # List (site filter)
    resp = await authed_client.get("/api/v1/strategies", params={"siteId": "plasmodb"})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == strategy_id
    assert items[0]["stepCount"] >= 1

    # Get
    resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
    assert resp.status_code == 200
    got = resp.json()
    assert got["id"] == strategy_id
    assert got["name"] == "My Strategy"

    # Update (name only)
    resp = await authed_client.patch(
        f"/api/v1/strategies/{strategy_id}",
        json={"name": "Renamed Strategy"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Strategy"

    # Delete
    resp = await authed_client.delete(f"/api/v1/strategies/{strategy_id}")
    assert resp.status_code == 204

    # Verify it is gone
    resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
    assert resp.status_code == 404
