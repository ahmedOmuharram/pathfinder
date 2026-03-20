"""Integration tests for gene set ensemble, reverse-search, and confidence endpoints."""

from uuid import UUID

import httpx
import jwt
import pytest

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.services.gene_sets.store import get_gene_set_store
from veupath_chatbot.services.gene_sets.types import GeneSet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user_id_from_client(authed_client: httpx.AsyncClient) -> UUID:
    """Extract user_id from the authed client cookie."""
    token = authed_client.cookies.get("pathfinder-auth")
    assert token is not None
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.api_secret_key,
        algorithms=["HS256"],
        options={"require": ["exp", "sub"]},
    )
    return UUID(payload["sub"])


def _seed_gene_set(
    user_id: UUID,
    *,
    gene_set_id: str,
    name: str = "Test Set",
    site_id: str = "PlasmoDB",
    gene_ids: list[str] | None = None,
    search_name: str | None = None,
) -> GeneSet:
    """Create and persist a gene set owned by the given user."""
    gs = GeneSet(
        id=gene_set_id,
        name=name,
        site_id=site_id,
        gene_ids=gene_ids or ["G1", "G2", "G3"],
        source="paste",
        user_id=user_id,
        search_name=search_name,
    )
    store = get_gene_set_store()
    store.save(gs)
    return gs


# ---------------------------------------------------------------------------
# Ensemble endpoint: POST /api/v1/gene-sets/ensemble
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensemble_returns_scores(authed_client: httpx.AsyncClient) -> None:
    """POST /ensemble returns ensemble frequency scores for genes across sets."""
    user_id = _user_id_from_client(authed_client)
    _seed_gene_set(user_id, gene_set_id="ens-a", gene_ids=["G1", "G2", "G3"])
    _seed_gene_set(user_id, gene_set_id="ens-b", gene_ids=["G1", "G3", "G4"])
    _seed_gene_set(user_id, gene_set_id="ens-c", gene_ids=["G1", "G5"])

    resp = await authed_client.post(
        "/api/v1/gene-sets/ensemble",
        json={
            "geneSetIds": ["ens-a", "ens-b", "ens-c"],
            "positiveControls": ["G1"],
        },
    )
    assert resp.status_code == 200, resp.text

    scores = resp.json()
    assert isinstance(scores, list)
    assert len(scores) > 0

    # G1 appears in all 3 sets -> frequency = 1.0
    g1 = next(s for s in scores if s["geneId"] == "G1")
    assert g1["frequency"] == pytest.approx(1.0)
    assert g1["count"] == 3
    assert g1["total"] == 3
    assert g1["inPositives"] is True

    # G4 appears in 1 set -> frequency = 1/3
    g4 = next(s for s in scores if s["geneId"] == "G4")
    assert g4["frequency"] == pytest.approx(1 / 3)
    assert g4["inPositives"] is False

    # Results should be sorted by frequency descending
    frequencies = [s["frequency"] for s in scores]
    assert frequencies == sorted(frequencies, reverse=True)


@pytest.mark.asyncio
async def test_ensemble_422_with_fewer_than_2_ids(
    authed_client: httpx.AsyncClient,
) -> None:
    """POST /ensemble returns 422 when fewer than 2 gene set IDs are provided."""
    resp = await authed_client.post(
        "/api/v1/gene-sets/ensemble",
        json={"geneSetIds": ["only-one"]},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ensemble_404_when_gene_set_not_found(
    authed_client: httpx.AsyncClient,
) -> None:
    """POST /ensemble returns 404 when a referenced gene set ID does not exist."""
    user_id = _user_id_from_client(authed_client)
    _seed_gene_set(user_id, gene_set_id="ens-exists", gene_ids=["G1"])

    resp = await authed_client.post(
        "/api/v1/gene-sets/ensemble",
        json={"geneSetIds": ["ens-exists", "nonexistent-id"]},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reverse search endpoint: POST /api/v1/gene-sets/reverse-search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reverse_search_returns_ranked_results(
    authed_client: httpx.AsyncClient,
) -> None:
    """POST /reverse-search ranks user's gene sets by recall of positive genes."""
    user_id = _user_id_from_client(authed_client)
    _seed_gene_set(
        user_id,
        gene_set_id="rs-good",
        name="Good Match",
        site_id="PlasmoDB",
        gene_ids=["G1", "G2", "G3"],
        search_name="GenesByTextSearch",
    )
    _seed_gene_set(
        user_id,
        gene_set_id="rs-poor",
        name="Poor Match",
        site_id="PlasmoDB",
        gene_ids=["G4", "G5"],
        search_name="GeneByLocusTag",
    )

    resp = await authed_client.post(
        "/api/v1/gene-sets/reverse-search",
        json={
            "positiveGeneIds": ["G1", "G2"],
            "siteId": "PlasmoDB",
        },
    )
    assert resp.status_code == 200, resp.text

    results = resp.json()
    assert isinstance(results, list)
    assert len(results) >= 2

    good = next(r for r in results if r["geneSetId"] == "rs-good")
    poor = next(r for r in results if r["geneSetId"] == "rs-poor")

    # "Good Match" has G1 and G2 -> recall = 1.0
    assert good["recall"] == pytest.approx(1.0)
    assert good["overlapCount"] == 2
    assert good["name"] == "Good Match"
    assert good["searchName"] == "GenesByTextSearch"

    # "Poor Match" has neither G1 nor G2 -> recall = 0.0
    assert poor["recall"] == pytest.approx(0.0)
    assert poor["overlapCount"] == 0

    # Results sorted by recall descending
    assert results[0]["recall"] >= results[-1]["recall"]


@pytest.mark.asyncio
async def test_reverse_search_empty_when_no_gene_sets_for_site(
    authed_client: httpx.AsyncClient,
) -> None:
    """POST /reverse-search returns [] when user has no gene sets for the site."""
    resp = await authed_client.post(
        "/api/v1/gene-sets/reverse-search",
        json={
            "positiveGeneIds": ["G1"],
            "siteId": "EmptySiteDB",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Confidence endpoint: POST /api/v1/gene-sets/confidence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confidence_returns_sorted_scores(
    authed_client: httpx.AsyncClient,
) -> None:
    """POST /confidence returns composite confidence scores sorted descending."""
    resp = await authed_client.post(
        "/api/v1/gene-sets/confidence",
        json={
            "tpIds": ["G1"],
            "fpIds": ["G2"],
            "fnIds": ["G3"],
            "tnIds": ["G4"],
            "ensembleScores": {"G1": 0.9, "G2": 0.1},
            "enrichmentGeneCounts": {"G1": 3, "G3": 1},
            "maxEnrichmentTerms": 5,
        },
    )
    assert resp.status_code == 200, resp.text

    scores = resp.json()
    assert isinstance(scores, list)
    assert len(scores) == 4

    # Verify response shape
    for s in scores:
        assert "geneId" in s
        assert "compositeScore" in s
        assert "classificationScore" in s
        assert "ensembleScore" in s
        assert "enrichmentScore" in s

    # G1 is TP (cls=1.0) + ens=0.9 + enrich=3/5=0.6 -> composite = (1.0+0.9+0.6)/3
    g1 = next(s for s in scores if s["geneId"] == "G1")
    assert g1["classificationScore"] == pytest.approx(1.0)
    assert g1["ensembleScore"] == pytest.approx(0.9)
    assert g1["enrichmentScore"] == pytest.approx(0.6)

    # G2 is a false positive (cls -1.0)
    g2 = next(s for s in scores if s["geneId"] == "G2")
    assert g2["classificationScore"] == pytest.approx(-1.0)

    # Results sorted by composite descending
    composites = [s["compositeScore"] for s in scores]
    assert composites == sorted(composites, reverse=True)


@pytest.mark.asyncio
async def test_confidence_handles_empty_optional_inputs(
    authed_client: httpx.AsyncClient,
) -> None:
    """POST /confidence works with minimal inputs (no ensemble/enrichment data)."""
    resp = await authed_client.post(
        "/api/v1/gene-sets/confidence",
        json={
            "tpIds": ["G1"],
            "fpIds": [],
            "fnIds": [],
            "tnIds": [],
        },
    )
    assert resp.status_code == 200, resp.text

    scores = resp.json()
    assert isinstance(scores, list)
    assert len(scores) == 1

    g1 = scores[0]
    assert g1["geneId"] == "G1"
    assert g1["classificationScore"] == pytest.approx(1.0)
    # No ensemble or enrichment data -> both should be 0.0
    assert g1["ensembleScore"] == pytest.approx(0.0)
    assert g1["enrichmentScore"] == pytest.approx(0.0)
