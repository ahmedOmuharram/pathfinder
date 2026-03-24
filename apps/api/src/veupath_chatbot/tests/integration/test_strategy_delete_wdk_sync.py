"""Integration tests for strategy deletion WDK sync setting.

By default, deleting a strategy from PathFinder should NOT delete it from WDK.
Only when the client explicitly passes deleteFromWdk=true should the WDK
counterpart be removed.
"""

from typing import Any

import httpx
import pytest
import respx

_BASE = "https://plasmodb.org/plasmo/service"


def _strategy_list_item(
    strategy_id: int = 200,
    name: str = "Test strategy",
) -> dict[str, Any]:
    return {
        "strategyId": strategy_id,
        "name": name,
        "description": "",
        "author": "Guest User",
        "rootStepId": 100,
        "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "signature": "abc123def456",
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-06T00:00:00Z",
        "lastViewed": "2026-03-06T00:00:00Z",
        "releaseVersion": "68",
        "isPublic": False,
        "isSaved": False,
        "isValid": True,
        "isDeleted": False,
        "isExample": False,
        "organization": "",
        "estimatedSize": 150,
        "nameOfFirstStep": "Organism",
        "leafAndTransformStepCount": 1,
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


def _step_get_response(
    step_id: int = 100,
    search_name: str = "GenesByTaxon",
    estimated_size: int = 150,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "customName": f"Step for {search_name}",
        "displayName": f"Step for {search_name}",
        "isFiltered": False,
        "estimatedSize": estimated_size,
        "hasCompleteStepAnalyses": False,
        "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "searchName": search_name,
        "searchConfig": {
            "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
        },
    }


def _setup_wdk_sync(
    wdk_respx: respx.Router,
    strategy_id: int = 800,
    name: str = "WDK Delete Test",
) -> None:
    """Register mocks for a single WDK strategy sync."""
    items = [_strategy_list_item(strategy_id=strategy_id, name=name)]
    wdk_respx.get(f"{_BASE}/users/current").respond(200, json={"id": 12345})
    wdk_respx.get(f"{_BASE}/users/12345/strategies").respond(200, json=items)
    # Auto-import gene set calls: strategy detail, step report, step detail
    wdk_respx.get(f"{_BASE}/users/12345/strategies/{strategy_id}").respond(
        200, json=_strategy_get_response(strategy_id=strategy_id, step_ids=[100])
    )
    wdk_respx.post(f"{_BASE}/users/12345/steps/100/reports/standard").respond(
        200, json={"records": [], "meta": {"totalCount": 0, "responseCount": 0}}
    )
    wdk_respx.get(f"{_BASE}/users/12345/steps/100").respond(
        200, json=_step_get_response(step_id=100)
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
    wdk_respx.get(url__regex=rf"{_BASE}/record-types/.*/searches/[^/]+$").respond(
        200, json=_valid_search_response
    )
    wdk_respx.post(url__regex=rf"{_BASE}/record-types/.*/searches/.*").respond(
        200, json=_valid_search_response
    )


async def _sync_and_get_id(
    authed_client: httpx.AsyncClient,
) -> str:
    """Sync WDK strategies and return the first strategy's local ID."""
    sync_resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync_resp.status_code == 200, sync_resp.text
    strategies = sync_resp.json()
    assert len(strategies) >= 1
    return strategies[0]["id"]


# ---------------------------------------------------------------------------
# Default behavior: WDK delete NOT called
# ---------------------------------------------------------------------------


class TestDeleteWithoutWdkSync:
    @pytest.mark.asyncio
    async def test_delete_without_param_does_not_call_wdk(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """DELETE /strategies/{id} without deleteFromWdk should NOT call WDK delete."""
        _setup_wdk_sync(wdk_respx)
        strategy_id = await _sync_and_get_id(authed_client)

        wdk_delete_route = wdk_respx.delete(
            f"{_BASE}/users/12345/strategies/800"
        ).respond(204)

        delete_resp = await authed_client.delete(f"/api/v1/strategies/{strategy_id}")
        assert delete_resp.status_code == 204

        assert not wdk_delete_route.called, (
            "Default DELETE must NOT call WDK delete endpoint"
        )

    @pytest.mark.asyncio
    async def test_delete_with_false_param_does_not_call_wdk(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """DELETE with deleteFromWdk=false should NOT call WDK delete."""
        _setup_wdk_sync(wdk_respx, strategy_id=801, name="Explicit False")
        strategy_id = await _sync_and_get_id(authed_client)

        wdk_delete_route = wdk_respx.delete(
            f"{_BASE}/users/12345/strategies/801"
        ).respond(204)

        delete_resp = await authed_client.delete(
            f"/api/v1/strategies/{strategy_id}",
            params={"deleteFromWdk": "false"},
        )
        assert delete_resp.status_code == 204

        assert not wdk_delete_route.called, (
            "deleteFromWdk=false must NOT call WDK delete endpoint"
        )

    @pytest.mark.asyncio
    async def test_local_records_always_deleted(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """Local CQRS records are deleted regardless of deleteFromWdk."""
        _setup_wdk_sync(wdk_respx, strategy_id=802, name="Always Local Delete")
        strategy_id = await _sync_and_get_id(authed_client)

        delete_resp = await authed_client.delete(f"/api/v1/strategies/{strategy_id}")
        assert delete_resp.status_code == 204

        get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert get_resp.status_code == 200, (
            "WDK-linked strategy must be soft-deleted (dismissed), not hard-deleted"
        )
        assert get_resp.json()["dismissedAt"] is not None


# ---------------------------------------------------------------------------
# Explicit opt-in: WDK delete IS called
# ---------------------------------------------------------------------------


class TestDeleteWithWdkSync:
    @pytest.mark.asyncio
    async def test_delete_with_true_param_calls_wdk(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """DELETE with deleteFromWdk=true SHOULD call WDK delete."""
        _setup_wdk_sync(wdk_respx, strategy_id=803, name="Explicit True")
        strategy_id = await _sync_and_get_id(authed_client)

        wdk_delete_route = wdk_respx.delete(
            f"{_BASE}/users/12345/strategies/803"
        ).respond(204)

        delete_resp = await authed_client.delete(
            f"/api/v1/strategies/{strategy_id}",
            params={"deleteFromWdk": "true"},
        )
        assert delete_resp.status_code == 204

        assert wdk_delete_route.called, (
            "deleteFromWdk=true must call WDK delete endpoint"
        )

    @pytest.mark.asyncio
    async def test_delete_with_wdk_sync_also_removes_local(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """deleteFromWdk=true deletes both WDK and local records."""
        _setup_wdk_sync(wdk_respx, strategy_id=804, name="Both Delete")
        strategy_id = await _sync_and_get_id(authed_client)

        wdk_respx.delete(f"{_BASE}/users/12345/strategies/804").respond(204)

        delete_resp = await authed_client.delete(
            f"/api/v1/strategies/{strategy_id}",
            params={"deleteFromWdk": "true"},
        )
        assert delete_resp.status_code == 204

        get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_wdk_delete_failure_still_deletes_local(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """If WDK delete fails, local records are still deleted."""
        _setup_wdk_sync(wdk_respx, strategy_id=805, name="WDK Fail")
        strategy_id = await _sync_and_get_id(authed_client)

        # WDK returns 500
        wdk_respx.delete(f"{_BASE}/users/12345/strategies/805").respond(500)

        delete_resp = await authed_client.delete(
            f"/api/v1/strategies/{strategy_id}",
            params={"deleteFromWdk": "true"},
        )
        assert delete_resp.status_code == 204

        get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert get_resp.status_code == 404, (
            "Local strategy must be deleted even if WDK delete fails"
        )


# ---------------------------------------------------------------------------
# Non-WDK strategies (no wdk_strategy_id)
# ---------------------------------------------------------------------------


class TestDeleteNonWdkStrategy:
    @pytest.mark.asyncio
    async def test_delete_local_only_strategy_ignores_param(
        self,
        authed_client: httpx.AsyncClient,
    ) -> None:
        """Local-only strategies (no WDK link) delete cleanly regardless of param."""
        create_resp = await authed_client.post(
            "/api/v1/strategies",
            json={
                "name": "Local Only",
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

        delete_resp = await authed_client.delete(
            f"/api/v1/strategies/{strategy_id}",
            params={"deleteFromWdk": "true"},
        )
        assert delete_resp.status_code == 204

        get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert get_resp.status_code == 404
