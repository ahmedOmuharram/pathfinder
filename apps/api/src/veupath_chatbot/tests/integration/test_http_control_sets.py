"""Integration tests for control set CRUD endpoints."""

from uuid import uuid4

import httpx
import pytest

import veupath_chatbot.persistence.session as session_module
from veupath_chatbot.persistence.models import ControlSet, User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_body(
    *,
    name: str = "Test Controls",
    site_id: str = "plasmodb",
    record_type: str = "gene",
    positive_ids: list[str] | None = None,
    negative_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "siteId": site_id,
        "recordType": record_type,
        "positiveIds": positive_ids or ["gene1", "gene2"],
        "negativeIds": negative_ids or ["gene3", "gene4"],
    }


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_control_sets_requires_auth(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/control-sets", params={"siteId": "plasmodb"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_control_set_requires_auth(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/control-sets", json=_create_body())
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_control_set_requires_auth(client: httpx.AsyncClient) -> None:
    resp = await client.get(f"/api/v1/control-sets/{uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_control_set_requires_auth(client: httpx.AsyncClient) -> None:
    resp = await client.delete(f"/api/v1/control-sets/{uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_control_set(authed_client: httpx.AsyncClient) -> None:
    """Creating a control set returns 201 with correct fields."""
    body = _create_body(name="My Controls", positive_ids=["a", "b"], negative_ids=["c"])
    resp = await authed_client.post("/api/v1/control-sets", json=body)
    assert resp.status_code == 201, resp.text

    cs = resp.json()
    assert cs["name"] == "My Controls"
    assert cs["siteId"] == "plasmodb"
    assert cs["recordType"] == "gene"
    assert cs["positiveIds"] == ["a", "b"]
    assert cs["negativeIds"] == ["c"]
    assert cs["version"] == 1
    assert cs["isPublic"] is False
    assert "id" in cs
    assert "createdAt" in cs


@pytest.mark.asyncio
async def test_create_control_set_with_tags(authed_client: httpx.AsyncClient) -> None:
    """Tags and provenance notes persist correctly."""
    body = {
        **_create_body(),
        "tags": ["malaria", "kinase"],
        "provenanceNotes": "From literature review",
        "source": "manual",
    }
    resp = await authed_client.post("/api/v1/control-sets", json=body)
    assert resp.status_code == 201

    cs = resp.json()
    assert cs["tags"] == ["malaria", "kinase"]
    assert cs["provenanceNotes"] == "From literature review"
    assert cs["source"] == "manual"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_control_sets_requires_site_id(
    authed_client: httpx.AsyncClient,
) -> None:
    """List without siteId returns a validation error."""
    resp = await authed_client.get("/api/v1/control-sets")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_control_sets_empty(authed_client: httpx.AsyncClient) -> None:
    """Empty site returns []."""
    resp = await authed_client.get(
        "/api/v1/control-sets", params={"siteId": "emptysite"}
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_control_sets_filters_by_site(
    authed_client: httpx.AsyncClient,
) -> None:
    """siteId filter returns only matching control sets."""
    await authed_client.post(
        "/api/v1/control-sets", json=_create_body(site_id="plasmodb", name="Plasmo CS")
    )
    await authed_client.post(
        "/api/v1/control-sets", json=_create_body(site_id="toxodb", name="Toxo CS")
    )

    resp = await authed_client.get(
        "/api/v1/control-sets", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200
    items = resp.json()
    assert all(cs["siteId"] == "plasmodb" for cs in items)
    assert any(cs["name"] == "Plasmo CS" for cs in items)
    assert not any(cs["name"] == "Toxo CS" for cs in items)


@pytest.mark.asyncio
async def test_list_control_sets_filters_by_tags(
    authed_client: httpx.AsyncClient,
) -> None:
    """tags filter returns only matching control sets."""
    await authed_client.post(
        "/api/v1/control-sets",
        json={**_create_body(name="Tagged CS"), "tags": ["malaria"]},
    )
    await authed_client.post(
        "/api/v1/control-sets",
        json={**_create_body(name="Untagged CS"), "tags": ["other"]},
    )

    resp = await authed_client.get(
        "/api/v1/control-sets", params={"siteId": "plasmodb", "tags": "malaria"}
    )
    assert resp.status_code == 200
    items = resp.json()
    assert any(cs["name"] == "Tagged CS" for cs in items)
    assert not any(cs["name"] == "Untagged CS" for cs in items)


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_control_set(authed_client: httpx.AsyncClient) -> None:
    """Get returns the full control set."""
    create_resp = await authed_client.post("/api/v1/control-sets", json=_create_body())
    assert create_resp.status_code == 201
    cs_id = create_resp.json()["id"]

    resp = await authed_client.get(f"/api/v1/control-sets/{cs_id}")
    assert resp.status_code == 200
    cs = resp.json()
    assert cs["id"] == cs_id
    assert cs["name"] == "Test Controls"
    assert cs["positiveIds"] == ["gene1", "gene2"]
    assert cs["negativeIds"] == ["gene3", "gene4"]


@pytest.mark.asyncio
async def test_get_control_set_not_found(authed_client: httpx.AsyncClient) -> None:
    """Non-existent control set returns 404."""
    resp = await authed_client.get(f"/api/v1/control-sets/{uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_control_set(authed_client: httpx.AsyncClient) -> None:
    """Owner can delete their control set."""
    create_resp = await authed_client.post("/api/v1/control-sets", json=_create_body())
    assert create_resp.status_code == 201
    cs_id = create_resp.json()["id"]

    resp = await authed_client.delete(f"/api/v1/control-sets/{cs_id}")
    assert resp.status_code == 204

    # Verify it is gone
    resp = await authed_client.get(f"/api/v1/control-sets/{cs_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_control_set_not_found(authed_client: httpx.AsyncClient) -> None:
    """Deleting a non-existent control set returns 404."""
    resp = await authed_client.delete(f"/api/v1/control-sets/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_control_set_wrong_owner(
    authed_client: httpx.AsyncClient,
) -> None:
    """Cannot delete a control set owned by another user.

    We insert a control set directly in the DB with a different user_id.
    """
    other_user_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(User(id=other_user_id))
        await session.flush()

        cs = ControlSet(
            name="Other's CS",
            site_id="plasmodb",
            record_type="gene",
            positive_ids=["x"],
            negative_ids=["y"],
            user_id=other_user_id,
        )
        session.add(cs)
        await session.flush()
        cs_id = str(cs.id)
        await session.commit()

    resp = await authed_client.delete(f"/api/v1/control-sets/{cs_id}")
    assert resp.status_code == 404
