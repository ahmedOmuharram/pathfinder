from uuid import uuid4

import httpx


async def test_begin_oversized_site_id_returns_422(
    authed_client: httpx.AsyncClient,
) -> None:
    conversation_id = str(uuid4())
    resp = await authed_client.post(
        f"/api/v1/conversations/{conversation_id}/begin",
        json={"siteId": "x" * 51},
    )
    assert resp.status_code == 422, resp.text
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_begin_unknown_experiment_returns_404(
    authed_client: httpx.AsyncClient,
) -> None:
    conversation_id = str(uuid4())
    resp = await authed_client.post(
        f"/api/v1/conversations/{conversation_id}/begin",
        json={"siteId": "plasmodb", "experimentId": "no-such-experiment"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_save_substrategy_on_empty_conversation_is_422(
    authed_client: httpx.AsyncClient,
) -> None:
    conversation_id = str(uuid4())
    begin = await authed_client.post(
        f"/api/v1/conversations/{conversation_id}/begin",
        json={"siteId": "plasmodb"},
    )
    assert begin.status_code in (200, 201), begin.text
    resp = await authed_client.post(
        f"/api/v1/conversations/{conversation_id}/save-substrategy",
        params={"siteId": "plasmodb"},
        json={"stepId": "0", "name": "x", "description": None},
    )
    assert resp.status_code == 422, resp.text
    assert resp.headers["content-type"].startswith("application/problem+json")
