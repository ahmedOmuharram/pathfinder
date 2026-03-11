"""Integration tests: lightweight refetch (GET /strategies) vs full sync (POST /sync-wdk).

Two features under test:

1. **Background auto-import**: POST /sync-wdk fires gene-set auto-import as a
   background task via ``spawn()`` and returns strategies immediately — it never
   blocks on gene-set resolution.

2. **Lightweight refetch**: GET /strategies reads from the local DB projection
   without calling WDK.  After mutations (dismiss, restore, rename), the list
   endpoint reflects changes without needing another POST /sync-wdk round-trip.
"""

import httpx
import pytest
import respx

from veupath_chatbot.tests.fixtures.wdk_responses import strategy_list_item

_BASE = "https://plasmodb.org/plasmo/service"


def _setup_wdk(
    wdk_respx: respx.Router,
    strategy_id: int = 900,
    name: str = "Test",
) -> None:
    items = [strategy_list_item(strategy_id=strategy_id, name=name)]
    wdk_respx.get(f"{_BASE}/users/current").respond(200, json={"id": "guest"})
    wdk_respx.get(f"{_BASE}/users/guest/strategies").respond(200, json=items)


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


# ---------------------------------------------------------------------------
# GET /strategies returns local projections without calling WDK
# ---------------------------------------------------------------------------


class TestListEndpointDoesNotSync:
    @pytest.mark.asyncio
    async def test_list_returns_strategies_without_wdk_sync(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """After sync-wdk populates projections, GET /strategies returns them
        without requiring another sync-wdk call."""
        _setup_wdk(wdk_respx, strategy_id=700, name="Refetch Test")
        strategy_id = await _sync_and_get_id(authed_client)

        # GET /strategies should return the strategy from the local DB.
        list_resp = await authed_client.get(
            "/api/v1/strategies", params={"siteId": "plasmodb"}
        )
        assert list_resp.status_code == 200
        ids = [s["id"] for s in list_resp.json()]
        assert strategy_id in ids

    @pytest.mark.asyncio
    async def test_delete_reflected_in_list_without_sync(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """After soft-delete (dismiss), GET /strategies omits the strategy and
        GET /strategies/dismissed includes it — no sync-wdk required."""
        _setup_wdk(wdk_respx, strategy_id=701, name="Delete Refetch")
        strategy_id = await _sync_and_get_id(authed_client)

        # Dismiss.
        delete_resp = await authed_client.delete(f"/api/v1/strategies/{strategy_id}")
        assert delete_resp.status_code == 204

        # Main list: strategy gone.
        list_resp = await authed_client.get(
            "/api/v1/strategies", params={"siteId": "plasmodb"}
        )
        assert list_resp.status_code == 200
        ids = [s["id"] for s in list_resp.json()]
        assert strategy_id not in ids

        # Dismissed list: strategy present.
        dismissed_resp = await authed_client.get(
            "/api/v1/strategies/dismissed", params={"siteId": "plasmodb"}
        )
        assert dismissed_resp.status_code == 200
        dismissed_ids = [s["id"] for s in dismissed_resp.json()]
        assert strategy_id in dismissed_ids

    @pytest.mark.asyncio
    async def test_restore_reflected_in_list_without_sync(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """After dismiss + restore, GET /strategies shows the strategy again
        without needing sync-wdk."""
        _setup_wdk(wdk_respx, strategy_id=702, name="Restore Refetch")
        strategy_id = await _sync_and_get_id(authed_client)

        # Dismiss then restore.
        await authed_client.delete(f"/api/v1/strategies/{strategy_id}")
        restore_resp = await authed_client.post(
            f"/api/v1/strategies/{strategy_id}/restore"
        )
        assert restore_resp.status_code == 200

        # Main list: strategy back.
        list_resp = await authed_client.get(
            "/api/v1/strategies", params={"siteId": "plasmodb"}
        )
        assert list_resp.status_code == 200
        ids = [s["id"] for s in list_resp.json()]
        assert strategy_id in ids

    @pytest.mark.asyncio
    async def test_rename_reflected_in_list_without_sync(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """After PATCH rename, GET /strategies shows the new name without
        needing sync-wdk."""
        _setup_wdk(wdk_respx, strategy_id=703, name="Old Name")
        strategy_id = await _sync_and_get_id(authed_client)

        # Rename via PATCH.
        patch_resp = await authed_client.patch(
            f"/api/v1/strategies/{strategy_id}",
            json={"name": "New Name"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["name"] == "New Name"

        # List reflects the rename without sync-wdk.
        list_resp = await authed_client.get(
            "/api/v1/strategies", params={"siteId": "plasmodb"}
        )
        assert list_resp.status_code == 200
        strategy = next(s for s in list_resp.json() if s["id"] == strategy_id)
        assert strategy["name"] == "New Name"


# ---------------------------------------------------------------------------
# POST /sync-wdk returns immediately (gene-set import is background)
# ---------------------------------------------------------------------------


class TestSyncWdkDoesNotBlockOnGeneImport:
    @pytest.mark.asyncio
    async def test_sync_wdk_returns_strategies_immediately(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """sync-wdk returns the synced strategy list without waiting for
        background gene-set auto-import to complete."""
        _setup_wdk(wdk_respx, strategy_id=704, name="Immediate Sync")

        sync_resp = await authed_client.post(
            "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
        )
        assert sync_resp.status_code == 200

        strategies = sync_resp.json()
        assert isinstance(strategies, list)
        assert len(strategies) >= 1

        # Verify the synced strategy is in the response.
        names = [s["name"] for s in strategies]
        assert "Immediate Sync" in names
