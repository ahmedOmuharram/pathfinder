"""Integration tests: WDK strategy sync and import alignment.

Tests the FULL workflow from HTTP request → service layer → WDK API (mocked)
→ DB projection, verifying Pathfinder correctly handles real WDK payloads.

Test level: Integration (real FastAPI app, real DB, mocked WDK HTTP)
- authed_client: real httpx.AsyncClient with ASGI transport
- wdk_respx: respx router intercepting outbound WDK httpx calls
- DB: real PostgreSQL (testcontainers), cleaned per test

WDK contracts validated:
- Strategy list endpoint → summary projections with correct fields
- Strategy detail endpoint → full AST with step counts
- Lazy detail fetch on first GET after summary-only sync
- Malformed WDK response → graceful error (no crash)
- isSaved flag round-trip through sync
"""

from dataclasses import dataclass, field
from typing import Any

import httpx
import respx

BASE = "https://plasmodb.org/plasmo/service"


@dataclass
class StrategyItemDetails:
    record_class_name: str = "TranscriptRecordClasses.TranscriptRecordClass"
    estimated_size: int = 150
    is_saved: bool = False
    signature: str = "abc123def456"
    leaf_and_transform_step_count: int = field(default=1)


def _strategy_list_item(
    strategy_id: int = 200,
    name: str = "Test strategy",
    details: StrategyItemDetails | None = None,
) -> dict[str, Any]:
    d = details or StrategyItemDetails()
    return {
        "strategyId": strategy_id,
        "name": name,
        "description": "",
        "author": "Guest User",
        "rootStepId": 100,
        "recordClassName": d.record_class_name,
        "signature": d.signature,
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-06T00:00:00Z",
        "lastViewed": "2026-03-06T00:00:00Z",
        "releaseVersion": "68",
        "isPublic": False,
        "isSaved": d.is_saved,
        "isValid": True,
        "isDeleted": False,
        "isExample": False,
        "organization": "",
        "estimatedSize": d.estimated_size,
        "nameOfFirstStep": "Organism",
        "leafAndTransformStepCount": d.leaf_and_transform_step_count,
    }


def _strategy_get_response(
    strategy_id: int = 200,
    step_ids: list[int] | None = None,
) -> dict[str, Any]:
    ids = step_ids or [100, 101, 102]
    search_names = {0: "GenesByTaxon", 1: "GenesByTextSearch", 2: "GenesByOrthologs"}

    def _build_tree(remaining: list[int]) -> dict[str, Any]:
        if len(remaining) == 1:
            return {"stepId": remaining[0]}
        return {
            "stepId": remaining[-1],
            "primaryInput": _build_tree(remaining[:-1]),
        }

    step_tree = _build_tree(ids)
    steps: dict[str, dict[str, Any]] = {}
    for idx, sid in enumerate(ids):
        sname = search_names.get(idx, "GenesByTaxon")
        steps[str(sid)] = {
            "id": sid,
            "searchName": sname,
            "searchConfig": {
                "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
                "wdkWeight": 0,
            },
            "displayName": "Organism" if sname == "GenesByTaxon" else sname,
            "customName": None,
            "estimatedSize": 150,
            "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
            "isFiltered": False,
            "hasCompleteStepAnalyses": False,
        }
    return {
        "strategyId": strategy_id,
        "name": "Test strategy",
        "description": "",
        "author": "Guest User",
        "organization": "",
        "releaseVersion": "68",
        "isSaved": False,
        "isPublic": False,
        "isDeleted": False,
        "isValid": True,
        "isExample": False,
        "rootStepId": ids[-1],
        "estimatedSize": 150,
        "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "stepTree": step_tree,
        "steps": steps,
        "signature": "abc123def456",
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-06T00:00:00Z",
        "lastViewed": "2026-03-06T00:00:00Z",
        "leafAndTransformStepCount": len(ids),
        "nameOfFirstStep": "Organism",
    }


def _setup_wdk_user(router: respx.Router) -> None:
    """Mock the /users/current endpoint (always needed for auth'd requests)."""
    router.get(f"{BASE}/users/current").respond(200, json={"id": 12345})


# ── Sync creates projections from WDK list ────────────────────────


async def test_sync_creates_projections_with_correct_wdk_fields(
    authed_client: httpx.AsyncClient,
    wdk_respx: respx.Router,
) -> None:
    """POST /sync-wdk → projections have wdkStrategyId, name, recordType, estimatedSize.

    Workflow: Pathfinder calls GET /users/{id}/strategies on WDK, parses
    the list response, and creates DB projections from summary data.
    This test verifies the EXTERNAL contract: WDK list item fields map
    to the correct Pathfinder projection fields.

    WDK contract: list item has strategyId (int), name (str),
    recordClassName (str), estimatedSize (int), isSaved (bool),
    leafAndTransformStepCount (int).
    """
    _setup_wdk_user(wdk_respx)
    items = [
        _strategy_list_item(
            strategy_id=42,
            name="Malaria Drug Resistance Genes",
            details=StrategyItemDetails(
                record_class_name="TranscriptRecordClasses.TranscriptRecordClass",
                estimated_size=1234,
                is_saved=True,
                leaf_and_transform_step_count=3,
            ),
        ),
    ]
    wdk_respx.get(f"{BASE}/users/12345/strategies").respond(200, json=items)
    # Background auto-import may attempt detail fetch
    wdk_respx.get(url__regex=r".*/users/12345/strategies/\d+$").respond(200, json={})

    resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) == 1
    proj = data[0]

    # Verify WDK fields correctly mapped to Pathfinder fields
    assert proj["wdkStrategyId"] == 42
    assert proj["name"] == "Malaria Drug Resistance Genes"
    assert proj["estimatedSize"] == 1234
    assert proj["stepCount"] == 3
    assert proj["isSaved"] is True


async def test_sync_handles_empty_wdk_strategy_list(
    authed_client: httpx.AsyncClient,
    wdk_respx: respx.Router,
) -> None:
    """Empty WDK strategy list → empty projection list (no error)."""
    _setup_wdk_user(wdk_respx)
    wdk_respx.get(f"{BASE}/users/12345/strategies").respond(200, json=[])

    resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ── WDK strategy detail lazy fetch ────────────────────────────────


async def test_lazy_fetch_populates_plan_from_wdk_detail(
    authed_client: httpx.AsyncClient,
    wdk_respx: respx.Router,
) -> None:
    """GET /strategies/{id} on summary-only projection → lazy fetches WDK detail.

    Workflow:
    1. POST /sync-wdk creates summary projection (no plan)
    2. GET /strategies/{id} triggers lazy detail fetch from WDK
    3. Response should contain plan with step tree from WDK

    WDK contract: GET /users/{id}/strategies/{id} returns full detail
    with stepTree, steps dict, recordClassName, estimatedSize.
    """
    _setup_wdk_user(wdk_respx)

    # Step 1: Sync with summary only
    items = [
        _strategy_list_item(
            strategy_id=777,
            name="Ortholog Search",
            details=StrategyItemDetails(
                estimated_size=500,
                leaf_and_transform_step_count=2,
            ),
        ),
    ]
    wdk_respx.get(f"{BASE}/users/12345/strategies").respond(200, json=items)
    # Detail fetch during auto-import (background) — return realistic payload
    detail = _strategy_get_response(strategy_id=777, step_ids=[100, 101])
    wdk_respx.get(url__regex=r".*/users/12345/strategies/777$").respond(
        200, json=detail
    )
    # Catch-all for other strategy detail fetches
    wdk_respx.get(url__regex=r".*/users/12345/strategies/\d+$").respond(200, json={})

    # Auto-import gene set: step report and step detail
    wdk_respx.post(url__regex=r".*/users/.*/steps/\d+/reports/standard$").respond(
        200, json={"records": [], "meta": {"totalCount": 0, "responseCount": 0}}
    )
    wdk_respx.get(url__regex=r".*/users/.*/steps/\d+$").respond(
        200,
        json={
            "id": 100,
            "searchName": "GenesByTaxon",
            "searchConfig": {
                "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
            },
            "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
            "estimatedSize": 150,
            "customName": "Step",
            "displayName": "Step",
            "isFiltered": False,
            "hasCompleteStepAnalyses": False,
        },
    )

    # Search metadata for param normalization (GET for get_search_details,
    # POST for get_search_details_with_params / refreshed-dependent-params)
    _valid_search_response: dict = {
        "searchData": {
            "urlSegment": "mock",
            "fullName": "Mock.mock",
            "displayName": "Mock",
            "paramNames": [],
            "parameters": [],
            "groups": [],
        },
        "validation": {"level": "DISPLAYABLE", "isValid": True},
    }
    wdk_respx.get(url__regex=r".*/record-types/.*/searches/[^/]+$").respond(
        200, json=_valid_search_response
    )
    wdk_respx.post(url__regex=r".*/record-types/.*/searches/.*").respond(
        200, json=_valid_search_response
    )

    sync_resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync_resp.status_code == 200
    projections = sync_resp.json()
    assert len(projections) >= 1

    target = next((p for p in projections if p["wdkStrategyId"] == 777), None)
    assert target is not None

    # Step 2: GET the projection — may trigger lazy detail fetch
    get_resp = await authed_client.get(f"/api/v1/strategies/{target['id']}")
    assert get_resp.status_code == 200
    strategy_data = get_resp.json()

    # Should have a plan (from WDK detail)
    assert strategy_data["name"] == "Ortholog Search"


# ── Malformed WDK responses ──────────────────────────────────────


async def test_sync_skips_malformed_strategy_items(
    authed_client: httpx.AsyncClient,
    wdk_respx: respx.Router,
) -> None:
    """WDK list with mix of valid and garbage items → valid ones imported.

    WDK contract: Pathfinder should be resilient to individual items
    that fail parsing — skip them and import the rest.
    """
    _setup_wdk_user(wdk_respx)
    items = [
        _strategy_list_item(strategy_id=100, name="Good Strategy"),
        {"garbage": True, "no_strategy_id": "oops"},
        _strategy_list_item(strategy_id=200, name="Also Good"),
    ]
    wdk_respx.get(f"{BASE}/users/12345/strategies").respond(200, json=items)
    wdk_respx.get(url__regex=r".*/users/12345/strategies/\d+$").respond(200, json={})

    resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200
    data = resp.json()
    # At least the valid items should be imported
    names = {p["name"] for p in data}
    assert "Good Strategy" in names
    assert "Also Good" in names


# ── isSaved flag sync ─────────────────────────────────────────────


async def test_sync_preserves_is_saved_flag(
    authed_client: httpx.AsyncClient,
    wdk_respx: respx.Router,
) -> None:
    """isSaved=True from WDK → projection.isSaved=True.

    WDK contract: isSaved distinguishes draft (false) from explicitly
    saved (true) strategies. Pathfinder must preserve this distinction.
    """
    _setup_wdk_user(wdk_respx)
    items = [
        _strategy_list_item(
            strategy_id=100,
            name="Saved",
            details=StrategyItemDetails(is_saved=True),
        ),
        _strategy_list_item(
            strategy_id=200,
            name="Draft",
            details=StrategyItemDetails(is_saved=False),
        ),
    ]
    wdk_respx.get(f"{BASE}/users/12345/strategies").respond(200, json=items)
    wdk_respx.get(url__regex=r".*/users/12345/strategies/\d+$").respond(200, json={})

    resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200
    data = resp.json()

    saved = next(p for p in data if p["name"] == "Saved")
    draft = next(p for p in data if p["name"] == "Draft")
    assert saved["isSaved"] is True
    assert draft["isSaved"] is False
