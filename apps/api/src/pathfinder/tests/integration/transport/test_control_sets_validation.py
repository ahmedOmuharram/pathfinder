import httpx
import pytest


@pytest.mark.parametrize("method", ["GET", "DELETE"])
async def test_control_set_malformed_id_returns_422(
    authed_client: httpx.AsyncClient, method: str
) -> None:
    resp = await authed_client.request(method, "/api/v1/control-sets/not-a-uuid")
    assert resp.status_code == 422, (method, resp.status_code, resp.text)
    assert resp.headers["content-type"].startswith("application/problem+json")
