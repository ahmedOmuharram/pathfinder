"""Integration tests for experiment CRUD endpoints."""

from unittest.mock import AsyncMock, patch

import httpx
import jwt
import pytest

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import Experiment, ExperimentConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_experiment(
    experiment_id: str,
    user_id: str,
    *,
    site_id: str = "plasmodb",
    name: str = "Test Experiment",
    record_type: str = "transcript",
    status: str = "completed",
) -> Experiment:
    """Build a minimal Experiment dataclass."""
    return Experiment(
        id=experiment_id,
        user_id=user_id,
        status=status,
        config=ExperimentConfig(
            site_id=site_id,
            record_type=record_type,
            search_name="GenesByTextSearch",
            parameters={"text": "kinase"},
            positive_controls=["gene1"],
            negative_controls=["gene2"],
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            name=name,
        ),
        created_at="2026-01-01T00:00:00Z",
    )


def _user_id_from_client(authed_client: httpx.AsyncClient) -> str:
    """Extract user_id string from the authed client cookie."""
    token = authed_client.cookies.get("pathfinder-auth")
    assert token is not None
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.api_secret_key,
        algorithms=["HS256"],
        options={"require": ["exp", "sub"]},
    )
    return payload["sub"]


async def _seed_experiment(
    authed_client: httpx.AsyncClient,
    *,
    experiment_id: str = "exp-test-001",
    name: str = "Test Experiment",
    site_id: str = "plasmodb",
) -> Experiment:
    """Create and persist an experiment owned by the authed user."""
    user_id = _user_id_from_client(authed_client)
    exp = _make_experiment(experiment_id, user_id, name=name, site_id=site_id)
    store = get_experiment_store()
    store.save(exp)
    return exp


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_experiments_requires_auth(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/experiments/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_experiment_requires_auth(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/experiments/exp-xyz")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_experiment_requires_auth(client: httpx.AsyncClient) -> None:
    resp = await client.delete("/api/v1/experiments/exp-xyz")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List experiments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_experiments_empty(authed_client: httpx.AsyncClient) -> None:
    """Empty experiment list returns []."""
    resp = await authed_client.get("/api/v1/experiments/")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_experiments_returns_summaries(
    authed_client: httpx.AsyncClient,
) -> None:
    """List returns experiment summaries with key fields."""
    exp = await _seed_experiment(authed_client)

    resp = await authed_client.get("/api/v1/experiments/")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1

    found = [e for e in items if e["id"] == exp.id]
    assert len(found) == 1
    summary = found[0]
    assert summary["name"] == "Test Experiment"
    assert summary["siteId"] == "plasmodb"
    assert summary["recordType"] == "transcript"
    assert summary["status"] == "completed"


@pytest.mark.asyncio
async def test_list_experiments_filters_by_site(
    authed_client: httpx.AsyncClient,
) -> None:
    """siteId query parameter filters experiments."""
    await _seed_experiment(
        authed_client, experiment_id="exp-plasmo", site_id="plasmodb"
    )
    await _seed_experiment(authed_client, experiment_id="exp-toxo", site_id="toxodb")

    resp = await authed_client.get(
        "/api/v1/experiments/", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200
    items = resp.json()
    assert all(e["siteId"] == "plasmodb" for e in items)
    assert any(e["id"] == "exp-plasmo" for e in items)
    assert not any(e["id"] == "exp-toxo" for e in items)


# ---------------------------------------------------------------------------
# Get experiment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_experiment(authed_client: httpx.AsyncClient) -> None:
    """Get returns full experiment details."""
    exp = await _seed_experiment(authed_client, experiment_id="exp-get-test")

    resp = await authed_client.get(f"/api/v1/experiments/{exp.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == exp.id
    assert body["status"] == "completed"
    assert "config" in body
    assert body["config"]["siteId"] == "plasmodb"
    assert body["config"]["name"] == "Test Experiment"


@pytest.mark.asyncio
async def test_get_experiment_not_found(authed_client: httpx.AsyncClient) -> None:
    """Non-existent experiment returns 404."""
    resp = await authed_client.get("/api/v1/experiments/exp-nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_experiment_wrong_user(authed_client: httpx.AsyncClient) -> None:
    """Experiment owned by a different user returns 403."""
    exp = _make_experiment("exp-other-user", "00000000-0000-0000-0000-000000000099")
    store = get_experiment_store()
    store.save(exp)

    resp = await authed_client.get("/api/v1/experiments/exp-other-user")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Patch experiment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_experiment_notes(authed_client: httpx.AsyncClient) -> None:
    """PATCH updates experiment notes."""
    exp = await _seed_experiment(authed_client, experiment_id="exp-patch-test")

    resp = await authed_client.patch(
        f"/api/v1/experiments/{exp.id}",
        json={"notes": "Updated notes"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["notes"] == "Updated notes"


# ---------------------------------------------------------------------------
# Delete experiment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_experiment(authed_client: httpx.AsyncClient) -> None:
    """Delete removes the experiment and returns 204."""
    exp = await _seed_experiment(authed_client, experiment_id="exp-delete-test")

    with patch(
        "veupath_chatbot.services.experiment.materialization.cleanup_experiment_strategy",
        new_callable=AsyncMock,
    ):
        resp = await authed_client.delete(f"/api/v1/experiments/{exp.id}")

    assert resp.status_code == 204

    # Verify it is gone
    resp = await authed_client.get(f"/api/v1/experiments/{exp.id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_experiment_not_found(authed_client: httpx.AsyncClient) -> None:
    """Deleting a non-existent experiment returns 404."""
    resp = await authed_client.delete("/api/v1/experiments/exp-nonexistent")
    assert resp.status_code == 404
