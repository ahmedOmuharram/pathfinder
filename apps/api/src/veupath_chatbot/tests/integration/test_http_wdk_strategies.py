import httpx
import respx

from veupath_chatbot.services.strategies.wdk_counts import _STEP_COUNTS_CACHE
from veupath_chatbot.tests.fixtures.wdk_responses import (
    StrategyItemDetails,
    strategy_list_item,
)


async def test_open_strategy_requires_site_id_when_creating_new(
    authed_client: httpx.AsyncClient,
) -> None:
    # When neither strategyId nor wdkStrategyId is provided, siteId is required.
    resp = await authed_client.post("/api/v1/strategies/open", json={})
    assert resp.status_code == 422


async def test_sync_wdk_deletes_internal_control_test_strategies(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    base = "https://plasmodb.org/plasmo/service"

    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.get(f"{base}/users/guest/strategies").respond(
        200,
        json=[
            {
                "strategyId": 329824883,
                "name": "__pathfinder_internal__:Pathfinder control test",
                "isSaved": False,
            }
        ],
    )
    delete_route = wdk_respx.delete(f"{base}/users/guest/strategies/329824883").respond(
        204
    )

    resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200, resp.text
    assert delete_route.called


# ---------------------------------------------------------------------------
# Lazy WDK sync — TDD RED phase
# ---------------------------------------------------------------------------


async def test_sync_wdk_creates_projections_from_summary_only(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """POST /sync-wdk creates projections using the list endpoint.

    The sync response is built from summary data.  Background auto-import
    of gene sets may fetch individual strategy details afterward.
    """
    base = "https://plasmodb.org/plasmo/service"

    items = [
        strategy_list_item(
            strategy_id=100,
            name="Strategy A",
            details=StrategyItemDetails(
                estimated_size=50, leaf_and_transform_step_count=2
            ),
        ),
        strategy_list_item(
            strategy_id=200,
            name="Strategy B",
            details=StrategyItemDetails(
                estimated_size=75, leaf_and_transform_step_count=1
            ),
        ),
        strategy_list_item(
            strategy_id=300,
            name="Strategy C",
            details=StrategyItemDetails(
                estimated_size=120, leaf_and_transform_step_count=3
            ),
        ),
    ]

    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.get(f"{base}/users/guest/strategies").respond(200, json=items)
    # Mock detail route — background auto-import may fetch details
    wdk_respx.get(url__regex=r".*/users/guest/strategies/\d+$").respond(200, json={})

    resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) == 3

    # Verify summary fields are populated from the list endpoint
    names = {s["name"] for s in data}
    assert names == {"Strategy A", "Strategy B", "Strategy C"}


async def test_sync_wdk_populates_record_type_and_counts(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """Sync populates recordType, stepCount, and resultCount from WDK summary."""
    base = "https://plasmodb.org/plasmo/service"

    items = [
        strategy_list_item(
            strategy_id=100,
            name="Organism Search",
            details=StrategyItemDetails(
                record_class_name="TranscriptRecordClasses.TranscriptRecordClass",
                estimated_size=150,
                leaf_and_transform_step_count=2,
            ),
        )
    ]

    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.get(f"{base}/users/guest/strategies").respond(200, json=items)
    # Background auto-import task may fetch individual strategy details to resolve
    # gene IDs; provide a catch-all mock so those calls don't fail the test.
    wdk_respx.get(url__regex=r".*/users/guest/strategies/\d+$").respond(200, json={})

    resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) == 1
    strategy = data[0]
    assert strategy["recordType"] == "TranscriptRecordClasses.TranscriptRecordClass"
    assert strategy["stepCount"] == 2
    assert strategy["resultCount"] == 150


async def test_get_strategy_lazy_loads_detail_for_summary_only_projection(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """GET /strategies/{id} triggers a lazy detail fetch when plan is empty."""
    base = "https://plasmodb.org/plasmo/service"

    # Step 1: Sync to create summary-only projection.
    # Note: all WDK mocks must be registered before the first sync call because
    # the background auto-import task runs inline and may call WDK detail endpoints.
    items = [strategy_list_item(strategy_id=500, name="Lazy Load Test")]
    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.get(f"{base}/users/guest/strategies").respond(200, json=items)

    # WDK detail for strategy 500 — used by both the background auto-import task
    # (during sync-wdk) and the lazy detail fetch (during GET /strategies/{id}).
    wdk_detail = {
        "strategyId": 500,
        "name": "Lazy Load Test",
        "description": "",
        "isSaved": False,
        "isPublic": False,
        "isDeleted": False,
        "isValid": True,
        "rootStepId": 100,
        "estimatedSize": 150,
        "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "signature": "abc123def456",
        "stepTree": {"stepId": 100},
        "steps": {
            "100": {
                "id": 100,
                "searchName": "GenesByTaxon",
                "searchConfig": {
                    "parameters": {
                        "organism": '["Plasmodium falciparum 3D7"]',
                    },
                    "wdkWeight": 0,
                },
                "displayName": "Organism",
                "customName": None,
                "estimatedSize": 150,
                "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
                "isFiltered": False,
                "hasCompleteStepAnalyses": False,
            }
        },
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-06T00:00:00Z",
    }
    detail_route = wdk_respx.get(f"{base}/users/guest/strategies/500").respond(
        200, json=wdk_detail
    )

    # Mock all WDK endpoints that lazy_fetch_wdk_detail and auto-import call:
    # - refreshed-dependent-params (parameter refresh)
    # - POST /record-types/.../searches/{name} (parameter normalization with context)
    # - GET /record-types/.../searches/{name} (search spec fallback)
    # - POST /steps/{id}/reports/* (gene ID resolution)
    # - GET /steps/{id} (search context extraction from step)
    wdk_respx.post(
        url__regex=r".*/record-types/.*/searches/.*/refreshed-dependent-params"
    ).respond(200, json={})
    wdk_respx.post(url__regex=r".*/record-types/.*/searches/[^/]+$").respond(
        200, json={}
    )
    wdk_respx.get(url__regex=r".*/record-types/.*/searches/.*").respond(200, json={})
    wdk_respx.post(url__regex=r".*/users/guest/steps/\d+/reports/.*").respond(
        200, json={"records": []}
    )
    wdk_respx.get(url__regex=r".*/users/guest/steps/\d+$").respond(200, json={})

    sync_resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync_resp.status_code == 200
    strategy_id = sync_resp.json()[0]["id"]  # The internal UUID

    # Step 2: GET the strategy — plan may already be populated by auto-import,
    # or will be populated by lazy detail fetch now.
    get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
    assert get_resp.status_code == 200

    strategy = get_resp.json()
    # Should have steps now (from the lazy fetch)
    assert len(strategy["steps"]) > 0
    assert strategy["steps"][0]["searchName"] == "GenesByTaxon"
    assert strategy["rootStepId"] is not None

    # The detail route SHOULD have been called (lazy fetch)
    assert detail_route.called, (
        "GET should trigger lazy detail fetch for summary-only projection"
    )

    # Step counts from estimatedSize should be injected into step responses
    step = strategy["steps"][0]
    assert step["resultCount"] == 150, (
        "Lazy fetch should populate resultCount from WDK estimatedSize"
    )


async def test_get_strategy_uses_cached_plan_no_wdk_calls(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """GET /strategies/{id} does NOT call WDK when plan is already populated."""
    _ = wdk_respx  # active so any WDK call raises
    # Create a local strategy with a plan (no WDK link)
    create_resp = await authed_client.post(
        "/api/v1/strategies",
        json={
            "name": "Local Strategy",
            "siteId": "plasmodb",
            "plan": {
                "recordType": "transcript",
                "root": {
                    "searchName": "GenesByTaxon",
                    "parameters": {
                        "organism": '["Plasmodium falciparum 3D7"]',
                    },
                },
            },
        },
    )
    assert create_resp.status_code == 201
    strategy_id = create_resp.json()["id"]

    # Mock WDK — if any WDK call is made, it would fail (no routes configured)
    # GET should succeed without any WDK calls since plan is populated
    get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
    assert get_resp.status_code == 200

    strategy = get_resp.json()
    assert strategy["name"] == "Local Strategy"
    assert len(strategy["steps"]) > 0


# ---------------------------------------------------------------------------
# Step counts — anonymous reports for leaf-only strategies
# ---------------------------------------------------------------------------


async def test_step_counts_uses_anonymous_reports_for_leaf_only(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """POST /step-counts for a leaf-only plan uses anonymous reports, not compilation.

    The anonymous report endpoint is:
    POST /record-types/{recordType}/searches/{searchName}/reports/standard

    For leaf-only strategies, this is called once per step (in parallel),
    instead of creating a temporary WDK strategy.
    """
    base = "https://plasmodb.org/plasmo/service"

    # Clear the module-level cache to avoid stale results
    _STEP_COUNTS_CACHE.clear()

    # Mock anonymous report endpoint — returns totalCount
    report_route = wdk_respx.post(
        url__regex=rf"{base}/record-types/.*/searches/.*/reports/standard"
    ).respond(
        200,
        json={
            "meta": {"totalCount": 42, "displayRange": {"start": 0, "end": 0}},
            "records": [],
        },
    )

    # Mock compile/strategy endpoints — these should NOT be called
    create_strategy_route = wdk_respx.post(f"{base}/users/current/strategies").respond(
        200, json={"id": 999}
    )

    resp = await authed_client.post(
        "/api/v1/strategies/step-counts",
        json={
            "siteId": "plasmodb",
            "plan": {
                "recordType": "transcript",
                "root": {
                    "searchName": "GenesByTaxon",
                    "parameters": {
                        "organism": '["Plasmodium falciparum 3D7"]',
                    },
                },
            },
        },
    )
    assert resp.status_code == 200

    data = resp.json()
    counts = data["counts"]
    # Should have exactly one step with count from anonymous report
    assert len(counts) == 1
    step_id = next(iter(counts))
    assert counts[step_id] == 42

    # Anonymous report SHOULD have been called
    assert report_route.called, "Leaf-only strategy should use anonymous reports"

    # Strategy creation should NOT have been called (no compilation needed)
    assert not create_strategy_route.called, (
        "Leaf-only strategy should NOT create a temporary WDK strategy"
    )

    _STEP_COUNTS_CACHE.clear()


async def test_lazy_fetch_multi_step_populates_all_counts(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """GET /strategies/{id} lazy fetch populates resultCount for all steps in a multi-step strategy."""
    base = "https://plasmodb.org/plasmo/service"

    # All WDK mocks must be registered before sync-wdk: the background auto-import
    # task runs inline and calls the strategy detail endpoint to resolve gene IDs.
    # WDK detail for strategy 600 — a 3-step strategy (2 leaves + 1 combine)
    wdk_detail = {
        "strategyId": 600,
        "name": "Multi Step Counts",
        "description": "",
        "isSaved": False,
        "isPublic": False,
        "isDeleted": False,
        "isValid": True,
        "rootStepId": 300,
        "estimatedSize": 42,
        "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "signature": "multi123",
        "stepTree": {
            "stepId": 300,
            "primaryInput": {"stepId": 100},
            "secondaryInput": {"stepId": 200},
        },
        "steps": {
            "100": {
                "id": 100,
                "searchName": "GenesByTaxon",
                "searchConfig": {
                    "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
                    "wdkWeight": 0,
                },
                "displayName": "Organism",
                "customName": None,
                "estimatedSize": 5000,
                "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
                "isFiltered": False,
                "hasCompleteStepAnalyses": False,
            },
            "200": {
                "id": 200,
                "searchName": "GenesByLocation",
                "searchConfig": {"parameters": {}, "wdkWeight": 0},
                "displayName": "Genomic Location",
                "customName": None,
                "estimatedSize": 300,
                "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
                "isFiltered": False,
                "hasCompleteStepAnalyses": False,
            },
            "300": {
                "id": 300,
                "searchName": "boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
                "searchConfig": {
                    "parameters": {"bq_operator": "INTERSECT"},
                    "wdkWeight": 0,
                },
                "displayName": "Intersect",
                "customName": None,
                "estimatedSize": 42,
                "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
                "isFiltered": False,
                "hasCompleteStepAnalyses": False,
            },
        },
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-06T00:00:00Z",
    }
    wdk_respx.get(f"{base}/users/guest/strategies/600").respond(200, json=wdk_detail)

    # Mock all WDK endpoints called by lazy_fetch_wdk_detail and auto-import:
    # - refreshed-dependent-params (parameter refresh)
    # - POST /record-types/.../searches/{name} (parameter normalization with context)
    # - GET /record-types/.../searches/{name} (search spec fallback)
    # - POST /steps/{id}/reports/* (gene ID resolution)
    # - GET /steps/{id} (search context extraction)
    wdk_respx.post(
        url__regex=r".*/record-types/.*/searches/.*/refreshed-dependent-params"
    ).respond(200, json={})
    wdk_respx.post(url__regex=r".*/record-types/.*/searches/[^/]+$").respond(
        200, json={}
    )
    wdk_respx.get(url__regex=r".*/record-types/.*/searches/.*").respond(200, json={})
    wdk_respx.post(url__regex=r".*/users/guest/steps/\d+/reports/.*").respond(
        200, json={"records": []}
    )
    wdk_respx.get(url__regex=r".*/users/guest/steps/\d+$").respond(200, json={})

    # Step 1: Sync to create summary-only projection
    items = [strategy_list_item(strategy_id=600, name="Multi Step Counts")]
    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.get(f"{base}/users/guest/strategies").respond(200, json=items)

    sync_resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync_resp.status_code == 200
    strategy_id = sync_resp.json()[0]["id"]

    # Step 2: GET the strategy — lazy fetch populates resultCount from the detail
    get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
    assert get_resp.status_code == 200

    strategy = get_resp.json()
    steps = strategy["steps"]
    assert len(steps) == 3

    counts_by_search = {s["searchName"]: s["resultCount"] for s in steps}
    assert counts_by_search["GenesByTaxon"] == 5000
    assert counts_by_search["GenesByLocation"] == 300
    assert (
        counts_by_search[
            "boolean_question_TranscriptRecordClasses_TranscriptRecordClass"
        ]
        == 42
    )
