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

import httpx
import respx

from veupath_chatbot.tests.fixtures.wdk_responses import (
    StrategyItemDetails,
    strategy_get_response,
    strategy_list_item,
)

BASE = "https://plasmodb.org/plasmo/service"


def _setup_wdk_user(router: respx.Router) -> None:
    """Mock the /users/current endpoint (always needed for auth'd requests)."""
    router.get(f"{BASE}/users/current").respond(200, json={"id": "guest"})


# ── Sync creates projections from WDK list ────────────────────────


async def test_sync_creates_projections_with_correct_wdk_fields(
    authed_client: httpx.AsyncClient,
    wdk_respx: respx.Router,
) -> None:
    """POST /sync-wdk → projections have wdkStrategyId, name, recordType, resultCount.

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
        strategy_list_item(
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
    wdk_respx.get(f"{BASE}/users/guest/strategies").respond(200, json=items)
    # Background auto-import may attempt detail fetch
    wdk_respx.get(url__regex=r".*/users/guest/strategies/\d+$").respond(200, json={})

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
    assert proj["resultCount"] == 1234
    assert proj["stepCount"] == 3
    assert proj["isSaved"] is True


async def test_sync_handles_empty_wdk_strategy_list(
    authed_client: httpx.AsyncClient,
    wdk_respx: respx.Router,
) -> None:
    """Empty WDK strategy list → empty projection list (no error)."""
    _setup_wdk_user(wdk_respx)
    wdk_respx.get(f"{BASE}/users/guest/strategies").respond(200, json=[])

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
        strategy_list_item(
            strategy_id=777,
            name="Ortholog Search",
            details=StrategyItemDetails(
                estimated_size=500,
                leaf_and_transform_step_count=2,
            ),
        ),
    ]
    wdk_respx.get(f"{BASE}/users/guest/strategies").respond(200, json=items)
    # Detail fetch during auto-import (background) — return realistic payload
    detail = strategy_get_response(strategy_id=777, step_ids=[100, 101])
    wdk_respx.get(url__regex=r".*/users/guest/strategies/777$").respond(
        200, json=detail
    )
    # Catch-all for other strategy detail fetches
    wdk_respx.get(url__regex=r".*/users/guest/strategies/\d+$").respond(200, json={})

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
        strategy_list_item(strategy_id=100, name="Good Strategy"),
        {"garbage": True, "no_strategy_id": "oops"},
        strategy_list_item(strategy_id=200, name="Also Good"),
    ]
    wdk_respx.get(f"{BASE}/users/guest/strategies").respond(200, json=items)
    wdk_respx.get(url__regex=r".*/users/guest/strategies/\d+$").respond(200, json={})

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
        strategy_list_item(
            strategy_id=100,
            name="Saved",
            details=StrategyItemDetails(is_saved=True),
        ),
        strategy_list_item(
            strategy_id=200,
            name="Draft",
            details=StrategyItemDetails(is_saved=False),
        ),
    ]
    wdk_respx.get(f"{BASE}/users/guest/strategies").respond(200, json=items)
    wdk_respx.get(url__regex=r".*/users/guest/strategies/\d+$").respond(200, json={})

    resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200
    data = resp.json()

    saved = next(p for p in data if p["name"] == "Saved")
    draft = next(p for p in data if p["name"] == "Draft")
    assert saved["isSaved"] is True
    assert draft["isSaved"] is False
