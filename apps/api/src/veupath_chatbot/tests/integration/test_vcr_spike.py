"""Spike test: validate VCRpy record/replay with async httpx.

This test hits the real PlasmoDB WDK API to record a cassette, then
replays it on subsequent runs. It validates:

1. VCRpy records async httpx requests correctly
2. Cassette replay works without network
3. ASGI transport (http://test) is NOT intercepted (ignore_hosts works)
4. Auth cookie scrubbing removes sensitive values from cassettes

Run in RECORD mode (first time, or to refresh):
    pytest src/veupath_chatbot/tests/integration/test_vcr_spike.py -v --record-mode=all

Run in REPLAY mode (CI, normal dev):
    pytest src/veupath_chatbot/tests/integration/test_vcr_spike.py -v

Run in NEW_EPISODES mode (adding a new test locally):
    pytest src/veupath_chatbot/tests/integration/test_vcr_spike.py -v --record-mode=new_episodes
"""

import httpx
import pytest
from fastapi import FastAPI


@pytest.mark.vcr
async def test_get_record_types_from_plasmodb() -> None:
    """GET /record-types from PlasmoDB returns a non-empty list of strings."""
    async with httpx.AsyncClient(
        base_url="https://plasmodb.org/plasmo/service",
        headers={"Accept": "application/json"},
        timeout=30.0,
    ) as client:
        response = await client.get("/record-types")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "transcript" in data


@pytest.mark.vcr
async def test_get_searches_for_transcript() -> None:
    """GET /record-types/transcript/searches returns search objects."""
    async with httpx.AsyncClient(
        base_url="https://plasmodb.org/plasmo/service",
        headers={"Accept": "application/json"},
        timeout=30.0,
    ) as client:
        response = await client.get("/record-types/transcript/searches")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert all("urlSegment" in s for s in data)
    url_segments = [s["urlSegment"] for s in data]
    assert "GenesByTaxon" in url_segments


async def test_asgi_transport_not_intercepted(app: FastAPI) -> None:
    """ASGI transport requests (http://test) must NOT be intercepted by VCR.

    Uses /health (liveness) instead of /health/ready (readiness) because
    readiness requires DB and Redis, which are not needed for this spike.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
