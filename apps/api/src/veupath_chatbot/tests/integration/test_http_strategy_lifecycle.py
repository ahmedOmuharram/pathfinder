"""Integration tests for strategy lifecycle flows.

Covers: multi-step CRUD, plan updates, delete with WDK cleanup,
open strategy flows, and state transitions.
"""

import httpx
import respx

from veupath_chatbot.tests.fixtures.wdk_responses import (
    step_get_response,
    strategy_get_response,
    strategy_list_item,
)

# ---------------------------------------------------------------------------
# Multi-step strategy CRUD
# ---------------------------------------------------------------------------


async def test_create_multi_step_strategy_with_combine(
    authed_client: httpx.AsyncClient,
) -> None:
    """POST /strategies with 2 searches + INTERSECT combine returns 3 steps wired correctly."""
    resp = await authed_client.post(
        "/api/v1/strategies",
        json={
            "name": "Multi Step",
            "siteId": "plasmodb",
            "plan": {
                "recordType": "transcript",
                "root": {
                    "searchName": "boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
                    "displayName": "Intersect",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "step_1",
                        "searchName": "GenesByTaxon",
                        "displayName": "Organism",
                        "parameters": {
                            "organism": '["Plasmodium falciparum 3D7"]',
                        },
                    },
                    "secondaryInput": {
                        "id": "step_2",
                        "searchName": "GenesByLocation",
                        "displayName": "Genomic Location",
                        "parameters": {},
                    },
                },
            },
        },
    )
    assert resp.status_code == 201

    strategy = resp.json()
    steps = strategy["steps"]
    assert len(steps) == 3

    # Root step should be the combine
    root_id = strategy["rootStepId"]
    root_step = next(s for s in steps if s["id"] == root_id)
    assert root_step["operator"] == "INTERSECT"
    assert root_step["primaryInputStepId"] is not None
    assert root_step["secondaryInputStepId"] is not None

    # Input steps should be leaves
    leaf_kinds = {s["kind"] for s in steps if s["id"] != root_id}
    assert leaf_kinds == {"search"}


async def test_update_strategy_plan_recounts_steps(
    authed_client: httpx.AsyncClient,
) -> None:
    """Create with 1 step, PATCH with 3-step plan → step_count updates."""
    # Create with single step
    create_resp = await authed_client.post(
        "/api/v1/strategies",
        json={
            "name": "Growing Strategy",
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
    assert create_resp.status_code == 201
    strategy_id = create_resp.json()["id"]
    assert len(create_resp.json()["steps"]) == 1

    # Update with 3-step plan (2 leaves + combine)
    update_resp = await authed_client.patch(
        f"/api/v1/strategies/{strategy_id}",
        json={
            "plan": {
                "recordType": "transcript",
                "root": {
                    "searchName": "boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
                    "displayName": "Union",
                    "operator": "UNION",
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
    assert update_resp.status_code == 200

    updated = update_resp.json()
    assert len(updated["steps"]) == 3

    # Verify list endpoint reflects new step count
    list_resp = await authed_client.get(
        "/api/v1/strategies", params={"siteId": "plasmodb"}
    )
    assert list_resp.status_code == 200
    summaries = list_resp.json()
    target = next(s for s in summaries if s["id"] == strategy_id)
    assert target["stepCount"] == 3


async def test_update_strategy_preserves_plan_on_name_only_patch(
    authed_client: httpx.AsyncClient,
) -> None:
    """PATCH with just a name change preserves the existing plan."""
    create_resp = await authed_client.post(
        "/api/v1/strategies",
        json={
            "name": "Original Name",
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
    assert create_resp.status_code == 201
    strategy_id = create_resp.json()["id"]
    original_steps = create_resp.json()["steps"]

    update_resp = await authed_client.patch(
        f"/api/v1/strategies/{strategy_id}",
        json={"name": "Updated Name"},
    )
    assert update_resp.status_code == 200

    updated = update_resp.json()
    assert updated["name"] == "Updated Name"
    assert len(updated["steps"]) == len(original_steps)
    assert updated["steps"][0]["searchName"] == "GenesByTaxon"


# ---------------------------------------------------------------------------
# Delete with WDK cleanup
# ---------------------------------------------------------------------------


async def test_delete_wdk_linked_strategy_does_not_call_wdk_by_default(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """DELETE /strategies/{id} for WDK-linked strategy does NOT call WDK delete by default."""
    base = "https://plasmodb.org/plasmo/service"

    # Step 1: Sync to create a WDK-linked projection
    items = [strategy_list_item(strategy_id=800, name="WDK To Delete")]
    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.get(f"{base}/users/guest/strategies").respond(200, json=items)
    # Auto-import gene set calls: strategy detail, step report, step detail
    wdk_respx.get(f"{base}/users/guest/strategies/800").respond(
        200, json=strategy_get_response(strategy_id=800, step_ids=[100])
    )
    wdk_respx.post(f"{base}/users/guest/steps/100/reports/standard").respond(
        200, json={"records": [], "meta": {"totalCount": 0, "responseCount": 0}}
    )
    wdk_respx.get(f"{base}/users/guest/steps/100").respond(
        200, json=step_get_response(step_id=100)
    )
    # Lazy-fetch of strategy detail triggers search details call for parameter
    # normalisation during GET /strategies/{id}; return valid WDKSearchResponse.
    _valid_search_response: dict = {
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
        200, json=_valid_search_response
    )
    wdk_respx.post(url__regex=rf"{base}/record-types/.*/searches/.*").respond(
        200, json=_valid_search_response
    )

    sync_resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync_resp.status_code == 200
    strategy_id = sync_resp.json()[0]["id"]

    # Step 2: Mock WDK delete endpoint
    wdk_delete_route = wdk_respx.delete(f"{base}/users/guest/strategies/800").respond(
        204
    )

    # Step 3: Delete the strategy (no deleteFromWdk param)
    delete_resp = await authed_client.delete(f"/api/v1/strategies/{strategy_id}")
    assert delete_resp.status_code == 204

    # Verify WDK delete was NOT called (default behavior)
    assert not wdk_delete_route.called, (
        "Default delete should NOT call WDK delete endpoint"
    )

    # Verify WDK-linked strategy is soft-deleted (dismissed), not hard-deleted
    get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["dismissedAt"] is not None


# ---------------------------------------------------------------------------
# Open strategy flows
# ---------------------------------------------------------------------------


async def test_open_new_conversation_creates_empty_stream(
    authed_client: httpx.AsyncClient,
) -> None:
    """POST /open with just siteId creates an empty stream."""
    resp = await authed_client.post(
        "/api/v1/strategies/open",
        json={"siteId": "plasmodb"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "strategyId" in data

    # GET the created stream — should have no steps
    strategy_id = data["strategyId"]
    get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
    assert get_resp.status_code == 200
    strategy = get_resp.json()
    assert strategy["steps"] == []
    assert strategy["siteId"] == "plasmodb"


async def test_open_existing_strategy_returns_same_id(
    authed_client: httpx.AsyncClient,
) -> None:
    """POST /open with strategyId returns the same strategy ID."""
    # Create a strategy first
    create_resp = await authed_client.post(
        "/api/v1/strategies",
        json={
            "name": "Existing",
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

    # Open with the strategy ID
    open_resp = await authed_client.post(
        "/api/v1/strategies/open",
        json={"strategyId": strategy_id},
    )
    assert open_resp.status_code == 200
    assert open_resp.json()["strategyId"] == strategy_id


async def test_open_wdk_strategy_imports_full_plan(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """POST /open with wdkStrategyId fetches full WDK detail and populates plan."""
    base = "https://plasmodb.org/plasmo/service"

    wdk_detail = {
        "strategyId": 900,
        "name": "Imported Strategy",
        "description": "From WDK",
        "isSaved": True,
        "isPublic": False,
        "isDeleted": False,
        "isValid": True,
        "rootStepId": 100,
        "estimatedSize": 200,
        "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "signature": "import123",
        "stepTree": {"stepId": 100},
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
                "estimatedSize": 200,
                "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
                "isFiltered": False,
                "hasCompleteStepAnalyses": False,
            }
        },
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-06T00:00:00Z",
    }

    _valid_search_response_900: dict = {
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

    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.get(f"{base}/users/guest/strategies/900").respond(200, json=wdk_detail)
    wdk_respx.post(
        url__regex=r".*/record-types/.*/searches/.*/refreshed-dependent-params"
    ).respond(200, json={})
    wdk_respx.get(url__regex=r".*/record-types/.*/searches/[^/]+$").respond(
        200, json=_valid_search_response_900
    )
    wdk_respx.post(url__regex=r".*/record-types/.*/searches/.*").respond(
        200, json=_valid_search_response_900
    )

    # Open the WDK strategy
    open_resp = await authed_client.post(
        "/api/v1/strategies/open",
        json={"wdkStrategyId": 900, "siteId": "plasmodb"},
    )
    assert open_resp.status_code == 200
    strategy_id = open_resp.json()["strategyId"]

    # GET the imported strategy — should have full plan with steps
    get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
    assert get_resp.status_code == 200
    strategy = get_resp.json()
    assert len(strategy["steps"]) == 1
    assert strategy["steps"][0]["searchName"] == "GenesByTaxon"
    assert strategy["steps"][0]["estimatedSize"] == 200
    assert strategy["wdkStrategyId"] == 900
    assert strategy["isSaved"] is True


async def test_open_same_wdk_strategy_twice_reuses_projection(
    authed_client: httpx.AsyncClient, wdk_respx: respx.Router
) -> None:
    """Opening the same WDK strategy ID twice returns the same projection (upsert)."""
    base = "https://plasmodb.org/plasmo/service"

    wdk_detail = {
        "strategyId": 901,
        "name": "Reopen Test",
        "description": "",
        "isSaved": False,
        "isPublic": False,
        "isDeleted": False,
        "isValid": True,
        "rootStepId": 100,
        "estimatedSize": 50,
        "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "signature": "reopen123",
        "stepTree": {"stepId": 100},
        "steps": {
            "100": {
                "id": 100,
                "searchName": "GenesByTaxon",
                "searchConfig": {
                    "parameters": {},
                    "wdkWeight": 0,
                },
                "displayName": "Organism",
                "customName": None,
                "estimatedSize": 50,
                "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
                "isFiltered": False,
                "hasCompleteStepAnalyses": False,
            }
        },
    }

    wdk_respx.get(f"{base}/users/current").respond(200, json={"id": "guest"})
    _valid_search_response_901: dict = {
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

    wdk_respx.get(f"{base}/users/guest/strategies/901").respond(200, json=wdk_detail)
    wdk_respx.post(
        url__regex=r".*/record-types/.*/searches/.*/refreshed-dependent-params"
    ).respond(200, json={})
    wdk_respx.get(url__regex=r".*/record-types/.*/searches/[^/]+$").respond(
        200, json=_valid_search_response_901
    )
    wdk_respx.post(url__regex=r".*/record-types/.*/searches/.*").respond(
        200, json=_valid_search_response_901
    )

    # Open once
    open1 = await authed_client.post(
        "/api/v1/strategies/open",
        json={"wdkStrategyId": 901, "siteId": "plasmodb"},
    )
    assert open1.status_code == 200
    id1 = open1.json()["strategyId"]

    # Open again — should reuse the same projection
    open2 = await authed_client.post(
        "/api/v1/strategies/open",
        json={"wdkStrategyId": 901, "siteId": "plasmodb"},
    )
    assert open2.status_code == 200
    id2 = open2.json()["strategyId"]

    assert id1 == id2, (
        "Opening the same WDK strategy twice should return the same stream"
    )
