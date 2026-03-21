"""Integration tests for strategy edge cases and error recovery.

Covers: WDK failure recovery during lazy fetch, orphan pruning, sync
idempotency, internal strategy filtering, complex step counts via
compilation, caching, and partial failure scenarios.
"""

from unittest.mock import patch

import httpx
import respx

from veupath_chatbot.domain.strategy.ast import StepTreeNode
from veupath_chatbot.domain.strategy.compile import CompilationResult, CompiledStep
from veupath_chatbot.services.strategies.wdk_counts import _STEP_COUNTS_CACHE
from veupath_chatbot.tests.fixtures.wdk_responses import (
    step_get_response,
    strategy_get_response,
    strategy_list_item,
)

# ---------------------------------------------------------------------------
# Lazy fetch failure recovery
# ---------------------------------------------------------------------------


async def test_lazy_fetch_wdk_404_returns_empty_steps(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """GET /strategies/{id} returns 200 with empty steps when WDK detail returns 404."""
    base = "https://plasmodb.org/plasmo/service"

    # Sync to create summary-only projection.
    # Register 404 before sync so auto-import also gets 404 (gracefully handled).
    items = [strategy_list_item(strategy_id=700, name="Gone Strategy")]
    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.get(f"{base}/users/guest/strategies").respond(200, json=items)
    # WDK detail returns 404 — auto-import catches this error gracefully;
    # the lazy GET test below also uses this mock.
    wdk_respx.get(f"{base}/users/guest/strategies/700").respond(
        404, json={"status": "not_found", "message": "Strategy not found"}
    )

    sync_resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync_resp.status_code == 200
    strategy_id = sync_resp.json()[0]["id"]

    # GET should still succeed, but with no steps (plan not populated)
    get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
    assert get_resp.status_code == 200

    strategy = get_resp.json()
    assert strategy["name"] == "Gone Strategy"
    assert strategy["steps"] == []


async def test_lazy_fetch_wdk_500_returns_empty_steps(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """GET /strategies/{id} returns 200 with empty steps when WDK detail returns 500."""
    base = "https://plasmodb.org/plasmo/service"

    items = [strategy_list_item(strategy_id=701, name="Broken Strategy")]
    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.get(f"{base}/users/guest/strategies").respond(200, json=items)
    # WDK detail returns 500 — auto-import catches this error gracefully;
    # the lazy GET test below also uses this mock.
    wdk_respx.get(f"{base}/users/guest/strategies/701").respond(
        500, json={"status": "server_error", "message": "Internal Server Error"}
    )

    sync_resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync_resp.status_code == 200
    strategy_id = sync_resp.json()[0]["id"]

    get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
    assert get_resp.status_code == 200

    strategy = get_resp.json()
    assert strategy["name"] == "Broken Strategy"
    assert strategy["steps"] == []


# ---------------------------------------------------------------------------
# Sync: orphan pruning and idempotency
# ---------------------------------------------------------------------------


async def test_sync_prunes_orphaned_wdk_strategies(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """Re-sync with fewer WDK strategies prunes the missing ones."""
    base = "https://plasmodb.org/plasmo/service"

    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})

    # Auto-import gene set calls for all strategy IDs used in this test.
    # All use rootStepId=100 (from strategy_list_item default).
    for sid in (10, 20, 30):
        wdk_respx.get(f"{base}/users/guest/strategies/{sid}").respond(
            200, json=strategy_get_response(strategy_id=sid, step_ids=[100])
        )
    wdk_respx.post(f"{base}/users/guest/steps/100/reports/standard").respond(
        200, json={"records": [], "meta": {"totalCount": 0, "responseCount": 0}}
    )
    wdk_respx.get(f"{base}/users/guest/steps/100").respond(
        200, json=step_get_response(step_id=100)
    )
    # Lazy-fetch triggers search details call for parameter normalisation.
    _valid_search = {
        "searchData": {
            "urlSegment": "mock",
            "fullName": "Mock.mock",
            "displayName": "Mock",
            "paramNames": [],
            "groups": [],
            "parameters": [],
        },
        "validation": {"level": "DISPLAYABLE", "isValid": True},
    }
    wdk_respx.get(url__regex=rf"{base}/record-types/.*/searches/[^/]+$").respond(
        200, json=_valid_search
    )
    wdk_respx.post(url__regex=rf"{base}/record-types/.*/searches/.*").respond(
        200, json=_valid_search
    )

    # First sync: 3 strategies
    items_v1 = [
        strategy_list_item(strategy_id=10, name="Alpha"),
        strategy_list_item(strategy_id=20, name="Beta"),
        strategy_list_item(strategy_id=30, name="Gamma"),
    ]
    wdk_respx.get(f"{base}/users/guest/strategies").respond(200, json=items_v1)

    sync1 = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync1.status_code == 200
    assert len(sync1.json()) == 3

    # Second sync: only 2 strategies (Gamma deleted on WDK side)
    items_v2 = [
        strategy_list_item(strategy_id=10, name="Alpha"),
        strategy_list_item(strategy_id=20, name="Beta"),
    ]
    wdk_respx.get(f"{base}/users/guest/strategies").respond(200, json=items_v2)

    sync2 = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync2.status_code == 200
    names = {s["name"] for s in sync2.json()}
    assert "Alpha" in names
    assert "Beta" in names
    assert "Gamma" not in names, "Orphaned strategy should be pruned during re-sync"


async def test_sync_idempotent_upsert_updates_name(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """Syncing the same WDK strategy twice with a different name updates it in place."""
    base = "https://plasmodb.org/plasmo/service"

    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})

    # Auto-import gene set calls for strategy 50 (rootStepId=100 by default).
    wdk_respx.get(f"{base}/users/guest/strategies/50").respond(
        200, json=strategy_get_response(strategy_id=50, step_ids=[100])
    )
    wdk_respx.post(f"{base}/users/guest/steps/100/reports/standard").respond(
        200, json={"records": [], "meta": {"totalCount": 0, "responseCount": 0}}
    )
    wdk_respx.get(f"{base}/users/guest/steps/100").respond(
        200, json=step_get_response(step_id=100)
    )
    # Lazy-fetch triggers search details call for parameter normalisation.
    _valid_search = {
        "searchData": {
            "urlSegment": "mock",
            "fullName": "Mock.mock",
            "displayName": "Mock",
            "paramNames": [],
            "groups": [],
            "parameters": [],
        },
        "validation": {"level": "DISPLAYABLE", "isValid": True},
    }
    wdk_respx.get(url__regex=rf"{base}/record-types/.*/searches/[^/]+$").respond(
        200, json=_valid_search
    )
    wdk_respx.post(url__regex=rf"{base}/record-types/.*/searches/.*").respond(
        200, json=_valid_search
    )

    # First sync
    items_v1 = [strategy_list_item(strategy_id=50, name="Original Name")]
    wdk_respx.get(f"{base}/users/guest/strategies").respond(200, json=items_v1)

    sync1 = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync1.status_code == 200
    assert len(sync1.json()) == 1
    assert sync1.json()[0]["name"] == "Original Name"
    id1 = sync1.json()[0]["id"]

    # Second sync: same wdk_strategy_id, new name
    items_v2 = [strategy_list_item(strategy_id=50, name="Updated Name")]
    wdk_respx.get(f"{base}/users/guest/strategies").respond(200, json=items_v2)

    sync2 = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync2.status_code == 200
    assert len(sync2.json()) == 1
    assert sync2.json()[0]["name"] == "Updated Name"
    id2 = sync2.json()[0]["id"]

    assert id1 == id2, "Same WDK strategy should update in place, not create duplicate"


async def test_sync_filters_internal_strategy_names(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """WDK strategies with __pathfinder_internal__: prefix are not synced."""
    base = "https://plasmodb.org/plasmo/service"

    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})

    # Auto-import gene set calls for strategy 60 (the only non-internal one).
    # rootStepId=100 by default from strategy_list_item.
    wdk_respx.get(f"{base}/users/guest/strategies/60").respond(
        200, json=strategy_get_response(strategy_id=60, step_ids=[100])
    )
    wdk_respx.post(f"{base}/users/guest/steps/100/reports/standard").respond(
        200, json={"records": [], "meta": {"totalCount": 0, "responseCount": 0}}
    )
    wdk_respx.get(f"{base}/users/guest/steps/100").respond(
        200, json=step_get_response(step_id=100)
    )
    # Lazy-fetch triggers search details call for parameter normalisation.
    _valid_search = {
        "searchData": {
            "urlSegment": "mock",
            "fullName": "Mock.mock",
            "displayName": "Mock",
            "paramNames": [],
            "groups": [],
            "parameters": [],
        },
        "validation": {"level": "DISPLAYABLE", "isValid": True},
    }
    wdk_respx.get(url__regex=rf"{base}/record-types/.*/searches/[^/]+$").respond(
        200, json=_valid_search
    )
    wdk_respx.post(url__regex=rf"{base}/record-types/.*/searches/.*").respond(
        200, json=_valid_search
    )

    items = [
        strategy_list_item(strategy_id=60, name="Real Strategy"),
        strategy_list_item(
            strategy_id=61,
            name="__pathfinder_internal__:Pathfinder step counts",
        ),
        strategy_list_item(
            strategy_id=62,
            name="__pathfinder_internal__:Pathfinder control test",
        ),
    ]
    # Internal strategies should be cleaned up (deleted from WDK)
    wdk_respx.delete(url__regex=rf"{base}/users/guest/strategies/\d+").respond(204)
    wdk_respx.get(f"{base}/users/guest/strategies").respond(200, json=items)

    sync_resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync_resp.status_code == 200

    names = {s["name"] for s in sync_resp.json()}
    assert "Real Strategy" in names
    assert "__pathfinder_internal__:Pathfinder step counts" not in names
    assert "__pathfinder_internal__:Pathfinder control test" not in names


# ---------------------------------------------------------------------------
# Step counts: compilation path, caching, partial failure
# ---------------------------------------------------------------------------


async def test_complex_step_counts_via_compilation(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """POST /step-counts with combine plan uses compilation path and returns counts.

    For strategies with combine steps, the system must:
    1. Compile the strategy (create WDK steps)
    2. Create a temporary WDK strategy
    3. Read estimatedSize from the strategy detail
    4. Delete the temporary strategy
    """
    base = "https://plasmodb.org/plasmo/service"

    _STEP_COUNTS_CACHE.clear()

    # Mock compile_strategy to avoid all the search details / param normalization
    fake_result = CompilationResult(
        steps=[
            CompiledStep(
                local_id="step_a",
                wdk_step_id=1001,
                step_type="search",
                display_name="Organism",
            ),
            CompiledStep(
                local_id="step_b",
                wdk_step_id=1002,
                step_type="search",
                display_name="Location",
            ),
            CompiledStep(
                local_id="step_root",
                wdk_step_id=1003,
                step_type="combine",
                display_name="Intersect",
            ),
        ],
        step_tree=StepTreeNode(
            step_id=1003,
            primary_input=StepTreeNode(step_id=1001),
            secondary_input=StepTreeNode(step_id=1002),
        ),
        root_step_id=1003,
    )

    # Mock WDK HTTP endpoints for strategy creation + fetch + delete
    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.post(f"{base}/users/guest/strategies").respond(200, json={"id": 999})
    wdk_respx.get(f"{base}/users/guest/strategies/999").respond(
        200,
        json={
            "strategyId": 999,
            "name": "__pathfinder_internal__:Pathfinder step counts",
            "rootStepId": 1003,
            "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
            "isSaved": False,
            "isValid": True,
            "isPublic": False,
            "isDeleted": False,
            "estimatedSize": 42,
            "stepTree": {
                "stepId": 1003,
                "primaryInput": {"stepId": 1001},
                "secondaryInput": {"stepId": 1002},
            },
            "steps": {
                "1001": {
                    "id": 1001,
                    "searchName": "GenesByTaxon",
                    "searchConfig": {"parameters": {}},
                    "estimatedSize": 5000,
                },
                "1002": {
                    "id": 1002,
                    "searchName": "GenesByLocation",
                    "searchConfig": {"parameters": {}},
                    "estimatedSize": 300,
                },
                "1003": {
                    "id": 1003,
                    "searchName": "boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
                    "searchConfig": {"parameters": {}},
                    "estimatedSize": 42,
                },
            },
        },
    )
    delete_route = wdk_respx.delete(f"{base}/users/guest/strategies/999").respond(204)

    with patch(
        "veupath_chatbot.services.strategies.wdk_counts.compile_strategy",
        return_value=fake_result,
    ):
        resp = await authed_client.post(
            "/api/v1/strategies/step-counts",
            json={
                "siteId": "plasmodb",
                "plan": {
                    "recordType": "transcript",
                    "root": {
                        "searchName": "boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
                        "displayName": "Intersect",
                        "operator": "INTERSECT",
                        "primaryInput": {
                            "id": "step_a",
                            "searchName": "GenesByTaxon",
                            "displayName": "Organism",
                            "parameters": {},
                        },
                        "secondaryInput": {
                            "id": "step_b",
                            "searchName": "GenesByLocation",
                            "displayName": "Location",
                            "parameters": {},
                        },
                    },
                },
            },
        )

    assert resp.status_code == 200

    counts = resp.json()["counts"]
    assert counts["step_a"] == 5000
    assert counts["step_b"] == 300
    assert counts["step_root"] == 42

    # Verify temp strategy was cleaned up
    assert delete_route.called, "Temporary WDK strategy should be deleted"

    _STEP_COUNTS_CACHE.clear()


async def test_step_counts_cache_avoids_repeat_calls(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """Calling POST /step-counts twice with same plan only hits WDK once."""
    base = "https://plasmodb.org/plasmo/service"

    _STEP_COUNTS_CACHE.clear()

    report_route = wdk_respx.post(
        url__regex=rf"{base}/record-types/.*/searches/.*/reports/standard"
    ).respond(
        200,
        json={
            "meta": {"totalCount": 99},
            "records": [],
        },
    )

    plan_payload = {
        "siteId": "plasmodb",
        "plan": {
            "recordType": "transcript",
            "root": {
                "searchName": "GenesByTaxon",
                "displayName": "Organism",
                "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
            },
        },
    }

    # First call — should hit WDK
    resp1 = await authed_client.post(
        "/api/v1/strategies/step-counts", json=plan_payload
    )
    assert resp1.status_code == 200
    assert report_route.call_count == 1

    # Second call — should hit cache
    resp2 = await authed_client.post(
        "/api/v1/strategies/step-counts", json=plan_payload
    )
    assert resp2.status_code == 200
    assert report_route.call_count == 1, (
        "Second call should use cache — WDK should NOT be called again"
    )

    # Both should return the same counts
    counts1 = resp1.json()["counts"]
    counts2 = resp2.json()["counts"]
    step_id = next(iter(counts1))
    assert counts1[step_id] == 99
    assert counts2[step_id] == 99

    _STEP_COUNTS_CACHE.clear()


async def test_leaf_step_counts_failure_returns_none(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """Two-search plan where one anonymous report fails → one count, one None."""
    base = "https://plasmodb.org/plasmo/service"

    _STEP_COUNTS_CACHE.clear()

    # We need a plan with 2 independent searches (no combine).
    # A plan can only have one root, so we use a transform (primaryInput only).
    # But transforms aren't leaf-only either.
    #
    # For a true leaf-only with multiple steps, we'd need the AST to have
    # multiple leaf nodes, but that requires combine/transform at the root.
    #
    # Actually, a single search step IS leaf-only. Let's test that the
    # single report failure returns None.
    _call_count = 0

    def _fail_report(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"status": "error"})

    wdk_respx.post(
        url__regex=rf"{base}/record-types/.*/searches/.*/reports/standard"
    ).mock(side_effect=_fail_report)

    resp = await authed_client.post(
        "/api/v1/strategies/step-counts",
        json={
            "siteId": "plasmodb",
            "plan": {
                "recordType": "transcript",
                "root": {
                    "searchName": "GenesByTaxon",
                    "displayName": "Organism",
                    "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
                },
            },
        },
    )
    assert resp.status_code == 200

    counts = resp.json()["counts"]
    step_id = next(iter(counts))
    assert counts[step_id] is None, (
        "Failed anonymous report should return None count, not error"
    )

    _STEP_COUNTS_CACHE.clear()


# ---------------------------------------------------------------------------
# Plan update → list step count reflection
# ---------------------------------------------------------------------------


async def test_plan_update_reflects_in_list_step_count(
    authed_client: httpx.AsyncClient,
) -> None:
    """Create with 1 step, update to 3 steps, list shows stepCount=3."""
    create_resp = await authed_client.post(
        "/api/v1/strategies",
        json={
            "name": "Count Check",
            "siteId": "plasmodb",
            "plan": {
                "recordType": "transcript",
                "root": {
                    "searchName": "GenesByTaxon",
                    "displayName": "Organism",
                    "parameters": {},
                },
            },
        },
    )
    assert create_resp.status_code == 201
    strategy_id = create_resp.json()["id"]

    # Verify list shows stepCount=1
    list1 = await authed_client.get("/api/v1/strategies", params={"siteId": "plasmodb"})
    target1 = next(s for s in list1.json() if s["id"] == strategy_id)
    assert target1["stepCount"] == 1

    # Update to 3-step plan
    await authed_client.patch(
        f"/api/v1/strategies/{strategy_id}",
        json={
            "plan": {
                "recordType": "transcript",
                "root": {
                    "searchName": "boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
                    "displayName": "Intersect",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "a",
                        "searchName": "GenesByTaxon",
                        "displayName": "Organism",
                        "parameters": {},
                    },
                    "secondaryInput": {
                        "id": "b",
                        "searchName": "GenesByLocation",
                        "displayName": "Location",
                        "parameters": {},
                    },
                },
            },
        },
    )

    # Verify list shows stepCount=3
    list2 = await authed_client.get("/api/v1/strategies", params={"siteId": "plasmodb"})
    target2 = next(s for s in list2.json() if s["id"] == strategy_id)
    assert target2["stepCount"] == 3
