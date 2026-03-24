"""Integration tests for strategy soft-delete (dismiss/restore)."""

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


def _setup_wdk(
    wdk_respx: respx.Router,
    strategy_id: int = 900,
    name: str = "Soft Delete Test",
) -> None:
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
    sync_resp = await authed_client.post(
        "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
    )
    assert sync_resp.status_code == 200, sync_resp.text
    strategies = sync_resp.json()
    assert len(strategies) >= 1
    return strategies[0]["id"]


class TestSoftDeleteWdkStrategy:
    @pytest.mark.asyncio
    async def test_delete_wdk_strategy_soft_deletes(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """DELETE of WDK-linked strategy (no deleteFromWdk) soft-deletes it."""
        _setup_wdk(wdk_respx, strategy_id=900)
        strategy_id = await _sync_and_get_id(authed_client)

        delete_resp = await authed_client.delete(f"/api/v1/strategies/{strategy_id}")
        assert delete_resp.status_code == 204

        # Strategy should NOT appear in the main list.
        list_resp = await authed_client.get(
            "/api/v1/strategies", params={"siteId": "plasmodb"}
        )
        assert list_resp.status_code == 200
        ids = [s["id"] for s in list_resp.json()]
        assert strategy_id not in ids

        # Strategy should appear in the dismissed list.
        dismissed_resp = await authed_client.get(
            "/api/v1/strategies/dismissed", params={"siteId": "plasmodb"}
        )
        assert dismissed_resp.status_code == 200
        dismissed_ids = [s["id"] for s in dismissed_resp.json()]
        assert strategy_id in dismissed_ids

        # Strategy should have dismissedAt set.
        dismissed_strategy = next(
            s for s in dismissed_resp.json() if s["id"] == strategy_id
        )
        assert dismissed_strategy["dismissedAt"] is not None

    @pytest.mark.asyncio
    async def test_soft_deleted_strategy_not_reimported_by_sync(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """WDK sync does NOT re-import a dismissed strategy."""
        _setup_wdk(wdk_respx, strategy_id=901, name="No Reimport")
        strategy_id = await _sync_and_get_id(authed_client)

        # Dismiss it.
        await authed_client.delete(f"/api/v1/strategies/{strategy_id}")

        # Sync again — the WDK strategy still exists, but it should stay dismissed.
        _setup_wdk(wdk_respx, strategy_id=901, name="No Reimport Updated")
        sync_resp = await authed_client.post(
            "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
        )
        assert sync_resp.status_code == 200
        ids = [s["id"] for s in sync_resp.json()]
        assert strategy_id not in ids

    @pytest.mark.asyncio
    async def test_get_dismissed_strategy_still_works(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """GET /strategies/{id} still returns a dismissed strategy."""
        _setup_wdk(wdk_respx, strategy_id=902, name="Still Gettable")
        strategy_id = await _sync_and_get_id(authed_client)

        await authed_client.delete(f"/api/v1/strategies/{strategy_id}")

        get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["dismissedAt"] is not None


class TestRestoreStrategy:
    @pytest.mark.asyncio
    async def test_restore_dismissed_strategy(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """POST /strategies/{id}/restore clears dismissedAt and restores to main list."""
        _setup_wdk(wdk_respx, strategy_id=903, name="Restorable")
        strategy_id = await _sync_and_get_id(authed_client)

        await authed_client.delete(f"/api/v1/strategies/{strategy_id}")

        restore_resp = await authed_client.post(
            f"/api/v1/strategies/{strategy_id}/restore"
        )
        assert restore_resp.status_code == 200
        body = restore_resp.json()
        assert body["dismissedAt"] is None
        assert body["id"] == strategy_id

        # Should appear in main list again.
        list_resp = await authed_client.get(
            "/api/v1/strategies", params={"siteId": "plasmodb"}
        )
        ids = [s["id"] for s in list_resp.json()]
        assert strategy_id in ids

    @pytest.mark.asyncio
    async def test_restore_non_dismissed_strategy_returns_error(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """Restoring a non-dismissed strategy returns a validation error."""
        _setup_wdk(wdk_respx, strategy_id=904, name="Not Dismissed")
        strategy_id = await _sync_and_get_id(authed_client)

        restore_resp = await authed_client.post(
            f"/api/v1/strategies/{strategy_id}/restore"
        )
        assert restore_resp.status_code == 422


class TestHardDeleteStillWorks:
    @pytest.mark.asyncio
    async def test_delete_with_wdk_sync_hard_deletes(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """DELETE with deleteFromWdk=true still hard-deletes."""
        _setup_wdk(wdk_respx, strategy_id=905, name="Hard Delete")
        strategy_id = await _sync_and_get_id(authed_client)

        wdk_respx.delete(f"{_BASE}/users/12345/strategies/905").respond(204)

        delete_resp = await authed_client.delete(
            f"/api/v1/strategies/{strategy_id}",
            params={"deleteFromWdk": "true"},
        )
        assert delete_resp.status_code == 204

        # Hard-deleted: 404 on GET.
        get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_non_wdk_strategy_hard_deletes(
        self,
        authed_client: httpx.AsyncClient,
    ) -> None:
        """Non-WDK strategies are always hard-deleted."""
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

        delete_resp = await authed_client.delete(f"/api/v1/strategies/{strategy_id}")
        assert delete_resp.status_code == 204

        get_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert get_resp.status_code == 404
