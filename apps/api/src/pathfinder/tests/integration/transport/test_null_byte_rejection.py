import httpx
import pytest

_SITE_ID_LIST_PATHS = [
    "/api/v1/conversations",
    "/api/v1/conversations/dismissed",
    "/api/v1/experiments/",
    "/api/v1/gene-sets",
]


@pytest.mark.parametrize("path", _SITE_ID_LIST_PATHS)
async def test_site_id_null_byte_returns_422(
    authed_client: httpx.AsyncClient, path: str
) -> None:
    response = await authed_client.get(path, params={"siteId": "\x00"})
    assert response.status_code == 422, (path, response.status_code, response.text)


@pytest.mark.parametrize("path", _SITE_ID_LIST_PATHS)
async def test_site_id_valid_value_is_accepted(
    authed_client: httpx.AsyncClient, path: str
) -> None:
    response = await authed_client.get(path, params={"siteId": "plasmodb"})
    assert response.status_code == 200, (path, response.status_code, response.text)
