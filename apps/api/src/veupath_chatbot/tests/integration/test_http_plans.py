import httpx


async def test_plan_session_crud(authed_client: httpx.AsyncClient) -> None:
    # Open (create) a plan session.
    resp = await authed_client.post("/api/v1/plans/open", json={"siteId": "plasmodb"})
    assert resp.status_code == 200
    plan_session_id = resp.json()["planSessionId"]
    assert plan_session_id

    # Newly created sessions are empty and should not appear in list.
    resp = await authed_client.get("/api/v1/plans", params={"siteId": "plasmodb"})
    assert resp.status_code == 200
    assert resp.json() == []

    # Fetch the session.
    resp = await authed_client.get(f"/api/v1/plans/{plan_session_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == plan_session_id
    assert body["siteId"] == "plasmodb"
    assert isinstance(body["messages"], list)

    # Update the title.
    resp = await authed_client.patch(
        f"/api/v1/plans/{plan_session_id}", json={"title": "My Plan"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "My Plan"

    # Delete the session.
    resp = await authed_client.delete(f"/api/v1/plans/{plan_session_id}")
    assert resp.status_code == 200

    # Verify it is gone.
    resp = await authed_client.get(f"/api/v1/plans/{plan_session_id}")
    assert resp.status_code == 404
