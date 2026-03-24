"""Integration tests for strategy-to-gene-set auto-import (TDD Red phase).

Every test in this file is expected to FAIL on the current codebase because:
1. stream_projections has no gene_set_id or gene_set_auto_imported columns
2. POST /sync-wdk never creates gene sets
3. No ON DELETE SET NULL FK exists between stream_projections and gene_sets
"""

from uuid import UUID

import httpx
import jwt
import pytest
import respx

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.services.gene_sets.store import get_gene_set_store

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE = "https://plasmodb.org/plasmo/service"
_GENE_IDS_A: list[str] = ["PF3D7_0100100", "PF3D7_0100200"]
_GENE_IDS_B: list[str] = ["PF3D7_0200100", "PF3D7_0200200", "PF3D7_0300100"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user_id_from_client(authed_client: httpx.AsyncClient) -> UUID:
    token = authed_client.cookies.get("pathfinder-auth")
    assert token is not None
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.api_secret_key,
        algorithms=["HS256"],
        options={"require": ["exp", "sub"]},
    )
    return UUID(payload["sub"])


def _wdk_list_item(
    strategy_id: int,
    name: str,
    root_step_id: int,
    *,
    record_class_name: str = "TranscriptRecordClasses.TranscriptRecordClass",
    estimated_size: int = 50,
) -> dict:
    return {
        "strategyId": strategy_id,
        "name": name,
        "rootStepId": root_step_id,
        "recordClassName": record_class_name,
        "estimatedSize": estimated_size,
        "leafAndTransformStepCount": 1,
        "isSaved": False,
        "isDeleted": False,
        "isValid": True,
        "isPublic": False,
        "isExample": False,
        "description": "",
        "signature": f"sig{strategy_id}",
        "author": "Guest User",
        "organization": "",
        "releaseVersion": "68",
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-11T00:00:00Z",
        "lastViewed": "2026-03-11T00:00:00Z",
        "nameOfFirstStep": "Organism",
    }


def _wdk_strategy_detail(
    strategy_id: int,
    root_step_id: int,
    name: str,
    *,
    record_class_name: str = "TranscriptRecordClasses.TranscriptRecordClass",
    estimated_size: int = 50,
) -> dict:
    return {
        "strategyId": strategy_id,
        "name": name,
        "description": "",
        "isSaved": False,
        "isPublic": False,
        "isDeleted": False,
        "isValid": True,
        "rootStepId": root_step_id,
        "estimatedSize": estimated_size,
        "recordClassName": record_class_name,
        "signature": f"sig{strategy_id}",
        "stepTree": {"stepId": root_step_id},
        "steps": {
            str(root_step_id): {
                "id": root_step_id,
                "searchName": "GenesByTaxon",
                "searchConfig": {
                    "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
                    "wdkWeight": 0,
                },
                "displayName": "Organism",
                "customName": None,
                "estimatedSize": estimated_size,
                "recordClassName": record_class_name,
                "isFiltered": False,
                "hasCompleteStepAnalyses": False,
            }
        },
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-11T00:00:00Z",
    }


def _step_report_response(gene_ids: list[str]) -> dict:
    return {
        "records": [
            {"id": [{"name": "source_id", "value": gid}], "attributes": {}}
            for gid in gene_ids
        ],
        "meta": {
            "totalCount": len(gene_ids),
            "displayTotalCount": len(gene_ids),
            "responseCount": len(gene_ids),
        },
    }


def _register_strategies_list(
    wdk_respx: respx.Router,
    items: list[dict],
) -> None:
    wdk_respx.get(f"{_BASE}/users/current").respond(200, json={"id": 12345})
    wdk_respx.get(f"{_BASE}/users/12345/strategies").respond(200, json=items)


def _register_gene_id_fetch(
    wdk_respx: respx.Router,
    strategy_id: int,
    root_step_id: int,
    name: str,
    gene_ids: list[str],
) -> None:
    wdk_respx.get(f"{_BASE}/users/12345/strategies/{strategy_id}").respond(
        200, json=_wdk_strategy_detail(strategy_id, root_step_id, name)
    )
    wdk_respx.post(
        f"{_BASE}/users/12345/steps/{root_step_id}/reports/standard"
    ).respond(200, json=_step_report_response(gene_ids))
    # _extract_step_search_context fetches step detail to get searchName/parameters
    wdk_respx.get(f"{_BASE}/users/12345/steps/{root_step_id}").respond(
        200,
        json={
            "id": root_step_id,
            "searchName": "GenesByTaxon",
            "searchConfig": {
                "parameters": {"organism": '["Plasmodium falciparum 3D7"]'}
            },
            "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        },
    )
    # Lazy-fetch of strategy detail triggers search details call for parameter
    # normalisation; return valid WDKSearchResponse.
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


# ---------------------------------------------------------------------------
# TestSyncCreatesGeneSets
# ---------------------------------------------------------------------------


class TestSyncCreatesGeneSets:
    @pytest.mark.asyncio
    async def test_sync_wdk_creates_gene_sets_for_new_strategies(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        items = [
            _wdk_list_item(42, "Malaria Kinases", root_step_id=101),
            _wdk_list_item(43, "P. falciparum Invasion", root_step_id=102),
        ]
        _register_strategies_list(wdk_respx, items)
        _register_gene_id_fetch(wdk_respx, 42, 101, "Malaria Kinases", _GENE_IDS_A)
        _register_gene_id_fetch(
            wdk_respx, 43, 102, "P. falciparum Invasion", _GENE_IDS_B
        )

        sync_resp = await authed_client.post(
            "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
        )
        assert sync_resp.status_code == 200, sync_resp.text

        gs_resp = await authed_client.get(
            "/api/v1/gene-sets", params={"siteId": "plasmodb"}
        )
        assert gs_resp.status_code == 200, gs_resp.text
        gene_sets = gs_resp.json()

        assert len(gene_sets) == 2, (
            f"Expected 2 auto-imported gene sets after sync, got {len(gene_sets)}"
        )
        for gs in gene_sets:
            assert gs["source"] == "strategy"

    @pytest.mark.asyncio
    async def test_sync_wdk_idempotent(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        items = [
            _wdk_list_item(44, "Kinases Run 1", root_step_id=103),
            _wdk_list_item(45, "Proteases Run 1", root_step_id=104),
        ]
        _register_strategies_list(wdk_respx, items)
        _register_gene_id_fetch(wdk_respx, 44, 103, "Kinases Run 1", _GENE_IDS_A)
        _register_gene_id_fetch(wdk_respx, 45, 104, "Proteases Run 1", _GENE_IDS_B)

        r1 = await authed_client.post(
            "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
        )
        assert r1.status_code == 200, r1.text

        r2 = await authed_client.post(
            "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
        )
        assert r2.status_code == 200, r2.text

        gs_resp = await authed_client.get(
            "/api/v1/gene-sets", params={"siteId": "plasmodb"}
        )
        assert gs_resp.status_code == 200
        gene_sets = gs_resp.json()

        assert len(gene_sets) == 2, (
            f"Second sync must not duplicate gene sets. Expected 2, got {len(gene_sets)}"
        )

    @pytest.mark.asyncio
    async def test_sync_wdk_skips_strategies_without_wdk_id(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        valid_item = _wdk_list_item(46, "Valid Strategy", root_step_id=105)
        invalid_item = {
            "name": "No ID Strategy",
            "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
            "estimatedSize": 30,
            "leafAndTransformStepCount": 1,
        }
        wdk_respx.get(f"{_BASE}/users/current").respond(200, json={"id": 12345})
        wdk_respx.get(f"{_BASE}/users/12345/strategies").respond(
            200, json=[valid_item, invalid_item]
        )
        _register_gene_id_fetch(wdk_respx, 46, 105, "Valid Strategy", _GENE_IDS_A)

        sync_resp = await authed_client.post(
            "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
        )
        assert sync_resp.status_code == 200, sync_resp.text

        gs_resp = await authed_client.get(
            "/api/v1/gene-sets", params={"siteId": "plasmodb"}
        )
        assert gs_resp.status_code == 200
        gene_sets = gs_resp.json()

        assert len(gene_sets) == 1, (
            f"Only the valid WDK item should produce a gene set; got {len(gene_sets)}"
        )
        assert gene_sets[0]["wdkStrategyId"] == 46


# ---------------------------------------------------------------------------
# TestDeletionBehavior
# ---------------------------------------------------------------------------


class TestDeletionBehavior:
    @pytest.mark.asyncio
    async def test_delete_gene_set_preserves_strategy(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        item = _wdk_list_item(50, "Deletion Test A", root_step_id=110)
        _register_strategies_list(wdk_respx, [item])
        _register_gene_id_fetch(wdk_respx, 50, 110, "Deletion Test A", _GENE_IDS_A)

        sync_resp = await authed_client.post(
            "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
        )
        assert sync_resp.status_code == 200
        strategies = sync_resp.json()
        assert len(strategies) == 1
        strategy_id = strategies[0]["id"]

        gs_resp = await authed_client.get(
            "/api/v1/gene-sets", params={"siteId": "plasmodb"}
        )
        gene_sets = gs_resp.json()
        assert len(gene_sets) == 1
        gene_set_id = gene_sets[0]["id"]

        del_resp = await authed_client.delete(f"/api/v1/gene-sets/{gene_set_id}")
        assert del_resp.status_code == 200, del_resp.text

        strategy_resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert strategy_resp.status_code == 200, (
            "Deleting the gene set must not cascade-delete the linked strategy"
        )

    @pytest.mark.asyncio
    async def test_delete_strategy_preserves_gene_set(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        item = _wdk_list_item(51, "Deletion Test B", root_step_id=111)
        _register_strategies_list(wdk_respx, [item])
        _register_gene_id_fetch(wdk_respx, 51, 111, "Deletion Test B", _GENE_IDS_A)
        wdk_respx.delete(f"{_BASE}/users/12345/strategies/51").respond(204)

        sync_resp = await authed_client.post(
            "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
        )
        assert sync_resp.status_code == 200
        strategy_id = sync_resp.json()[0]["id"]

        gs_resp = await authed_client.get(
            "/api/v1/gene-sets", params={"siteId": "plasmodb"}
        )
        gene_sets = gs_resp.json()
        assert len(gene_sets) == 1
        gene_set_id = gene_sets[0]["id"]

        del_strategy_resp = await authed_client.delete(
            f"/api/v1/strategies/{strategy_id}"
        )
        assert del_strategy_resp.status_code == 204, del_strategy_resp.text

        get_gs_resp = await authed_client.get(f"/api/v1/gene-sets/{gene_set_id}")
        assert get_gs_resp.status_code == 200, (
            "Deleting the strategy must not cascade-delete the linked gene set"
        )
        assert get_gs_resp.json()["id"] == gene_set_id

    @pytest.mark.asyncio
    async def test_delete_gene_set_then_resync_no_regenerate(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        """Most critical test: user deletion intent persists across sync cycles."""
        item = _wdk_list_item(52, "No Regen After Delete", root_step_id=112)
        _register_strategies_list(wdk_respx, [item])
        _register_gene_id_fetch(
            wdk_respx, 52, 112, "No Regen After Delete", _GENE_IDS_A
        )

        r1 = await authed_client.post(
            "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
        )
        assert r1.status_code == 200

        gene_sets_initial = (
            await authed_client.get("/api/v1/gene-sets", params={"siteId": "plasmodb"})
        ).json()
        assert len(gene_sets_initial) == 1
        gene_set_id = gene_sets_initial[0]["id"]

        # User deliberately deletes the gene set
        del_resp = await authed_client.delete(f"/api/v1/gene-sets/{gene_set_id}")
        assert del_resp.status_code == 200, del_resp.text

        after_del = (
            await authed_client.get("/api/v1/gene-sets", params={"siteId": "plasmodb"})
        ).json()
        assert len(after_del) == 0, "Gene set must be gone after DELETE"

        # Second sync — same WDK data
        r2 = await authed_client.post(
            "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
        )
        assert r2.status_code == 200

        # Clear the in-memory cache so GET reads fresh DB state
        get_gene_set_store()._cache.clear()

        gene_sets_after_resync = (
            await authed_client.get("/api/v1/gene-sets", params={"siteId": "plasmodb"})
        ).json()

        assert len(gene_sets_after_resync) == 0, (
            "Re-sync must NOT recreate a gene set the user deliberately deleted. "
            f"Unexpected gene sets: {gene_sets_after_resync}"
        )


# ---------------------------------------------------------------------------
# TestGeneSetContents
# ---------------------------------------------------------------------------


class TestGeneSetContents:
    @pytest.mark.asyncio
    async def test_auto_imported_gene_set_has_strategy_metadata(
        self,
        authed_client: httpx.AsyncClient,
        wdk_respx: respx.Router,
    ) -> None:
        item = _wdk_list_item(
            60,
            "Malaria Invasion Genes",
            root_step_id=120,
            record_class_name="TranscriptRecordClasses.TranscriptRecordClass",
            estimated_size=len(_GENE_IDS_A),
        )
        _register_strategies_list(wdk_respx, [item])
        _register_gene_id_fetch(
            wdk_respx, 60, 120, "Malaria Invasion Genes", _GENE_IDS_A
        )

        sync_resp = await authed_client.post(
            "/api/v1/strategies/sync-wdk", params={"siteId": "plasmodb"}
        )
        assert sync_resp.status_code == 200, sync_resp.text

        gs_resp = await authed_client.get(
            "/api/v1/gene-sets", params={"siteId": "plasmodb"}
        )
        assert gs_resp.status_code == 200
        gene_sets = gs_resp.json()
        assert len(gene_sets) == 1

        gs = gene_sets[0]
        assert gs["source"] == "strategy"
        assert gs["wdkStrategyId"] == 60
        assert gs["name"] == "Malaria Invasion Genes"
        assert gs["recordType"] == "TranscriptRecordClasses.TranscriptRecordClass"
        assert set(gs["geneIds"]) == set(_GENE_IDS_A)
        assert gs["siteId"] == "plasmodb"
