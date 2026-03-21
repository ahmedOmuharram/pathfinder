"""Integration tests for strategy deletion WDK sync setting.

By default, deleting a strategy from PathFinder should NOT delete it from WDK.
Only when the client explicitly passes deleteFromWdk=true should the WDK
counterpart be removed.
"""

import httpx
import pytest
import respx

from veupath_chatbot.tests.fixtures.wdk_responses import (
    step_get_response,
    strategy_get_response,
    strategy_list_item,
)

_BASE = "https://plasmodb.org/plasmo/service"


def _setup_wdk_sync(
    wdk_respx: respx.Router,
    strategy_id: int = 800,
    name: str = "WDK Delete Test",
) -> None:
    """Register mocks for a single WDK strategy sync."""
    items = [strategy_list_item(strategy_id=strategy_id, name=name)]
    wdk_respx.get(f"{_BASE}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.get(f"{_BASE}/users/guest/strategies").respond(200, json=items)
    # Auto-import gene set calls: strategy detail, step report, step detail
    wdk_respx.get(f"{_BASE}/users/guest/strategies/{strategy_id}").respond(
        200, json=strategy_get_response(strategy_id=strategy_id, step_ids=[100])
    )
    wdk_respx.post(f"{_BASE}/users/guest/steps/100/reports/standard").respond(
        200, json={"records": [], "meta": {"totalCount": 0, "responseCount": 0}}
    )
    wdk_respx.get(f"{_BASE}/users/guest/steps/100").respond(
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
            f"{_BASE}/users/guest/strategies/800"
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
            f"{_BASE}/users/guest/strategies/801"
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
            f"{_BASE}/users/guest/strategies/803"
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

        wdk_respx.delete(f"{_BASE}/users/guest/strategies/804").respond(204)

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
        wdk_respx.delete(f"{_BASE}/users/guest/strategies/805").respond(500)

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
