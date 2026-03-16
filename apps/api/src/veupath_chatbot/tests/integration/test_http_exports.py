"""Integration test for the export download endpoint."""

import pytest
from httpx import AsyncClient

import veupath_chatbot.services.export as _export_mod
from veupath_chatbot.services.export import get_export_service
from veupath_chatbot.services.gene_sets.types import GeneSet


@pytest.fixture(autouse=True)
def _reset_export_singleton():
    _export_mod._service = None
    yield
    _export_mod._service = None


@pytest.mark.anyio
async def test_download_export_round_trip(client: AsyncClient) -> None:
    """Store an export via service, then GET it via the HTTP endpoint."""
    gs = GeneSet(
        id="gs-integ",
        name="IntegrationTest",
        site_id="PlasmoDB",
        gene_ids=["PF3D7_0100100", "PF3D7_0100200"],
        source="paste",
    )
    svc = get_export_service()
    result = await svc.export_gene_set(gs, "csv")

    response = await client.get(result.url)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="IntegrationTest.csv"' in response.headers["content-disposition"]
    body = response.text
    assert "gene_id" in body
    assert "PF3D7_0100100" in body


@pytest.mark.anyio
async def test_download_missing_export_404(client: AsyncClient) -> None:
    """GET a nonexistent export ID returns 404."""
    response = await client.get("/api/v1/exports/nonexistent-id")
    assert response.status_code == 404
