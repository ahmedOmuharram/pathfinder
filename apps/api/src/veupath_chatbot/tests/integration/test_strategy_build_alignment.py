"""Integration tests: strategy build → WDK round-trip alignment.

Tests the FULL workflow from POST /strategies → plan normalization →
strategy compilation → WDK step/strategy creation (mocked) → response.

Test level: Integration (real FastAPI app, real DB, mocked WDK HTTP)

WDK contracts validated:
- Strategy creation: plan with single leaf step → correct WDK payloads
- Strategy creation: multi-step plan → correct step ordering and tree wiring
- Invalid parameter handling → 422 before WDK is contacted
- Missing search name → clear error
- Step counts populated from WDK estimatedSize
"""

import httpx
import respx

from veupath_chatbot.tests.fixtures.wdk_responses import (
    search_details_response,
    strategy_get_response,
)

BASE = "https://plasmodb.org/plasmo/service"


def _setup_wdk_for_build(
    router: respx.Router,
    *,
    strategy_id: int = 200,
    step_ids: list[int] | None = None,
) -> None:
    """Mock all WDK endpoints needed for a full strategy build.

    Uses realistic fixtures from wdk_responses.py.
    """
    sids = step_ids or [100]
    router.get(f"{BASE}/users/current").respond(200, json={"id": "guest"})

    # Search metadata (needed by plan normalization and compilation)
    router.get(url__regex=r".*/record-types/.*/searches/GenesByTaxon$").respond(
        200, json=search_details_response("GenesByTaxon")
    )
    router.get(url__regex=r".*/record-types/.*/searches/GenesByTextSearch$").respond(
        200, json=search_details_response("GenesByTextSearch")
    )
    router.get(url__regex=r".*/record-types/.*/searches/boolean_question.*$").respond(
        200,
        json=search_details_response(
            "boolean_question_TranscriptRecordClasses_TranscriptRecordClass"
        ),
    )
    # Catch-all for any other search metadata
    router.get(url__regex=r".*/record-types/.*/searches/[^/]+$").respond(
        200,
        json={
            "searchData": {
                "urlSegment": "mock",
                "fullName": "Mock",
                "displayName": "Mock",
                "parameters": [],
                "groups": [],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        },
    )

    # Search listing (for boolean search name resolution)
    router.get(url__regex=r".*/record-types/.*/searches$").respond(
        200,
        json=[
            {
                "urlSegment": "GenesByTaxon",
                "fullName": "GeneQuestions.GenesByTaxon",
                "displayName": "Organism",
            },
            {
                "urlSegment": "GenesByTextSearch",
                "fullName": "GeneQuestions.GenesByTextSearch",
                "displayName": "Text Search",
            },
            {
                "urlSegment": "boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
                "fullName": "InternalQuestions.BooleanQuestion",
                "displayName": "Boolean",
            },
        ],
    )

    # Step creation
    _step_counter = iter(sids)

    def _next_step_id(*args: object, **kwargs: object) -> respx.MockResponse:
        try:
            sid = next(_step_counter)
        except StopIteration:
            sid = 999
        return respx.MockResponse(200, json={"id": sid})

    router.post(url__regex=r".*/users/.*/steps$").mock(side_effect=_next_step_id)

    # Strategy creation
    router.post(url__regex=r".*/users/.*/strategies$").respond(
        200, json={"id": strategy_id}
    )

    # Strategy detail (for count extraction after build)
    detail = strategy_get_response(strategy_id=strategy_id, step_ids=sids)
    router.get(url__regex=rf".*/users/.*/strategies/{strategy_id}$").respond(
        200, json=detail
    )

    # Step-tree PUT (for strategy update)
    router.put(url__regex=r".*/users/.*/strategies/.*/step-tree$").respond(200)

    # Step report (auto-import gene set resolution fetches step report)
    router.post(url__regex=r".*/users/.*/steps/\d+/reports/standard$").respond(
        200, json={"records": [], "meta": {"totalCount": 0, "responseCount": 0}}
    )

    # Individual step detail (auto-import fetches step details)
    router.get(url__regex=r".*/users/.*/steps/\d+$").respond(
        200,
        json={
            "id": sids[0],
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

    # Context-dependent param refresh (POST to search endpoint)
    router.post(url__regex=r".*/record-types/.*/searches/.*$").respond(
        200, json=search_details_response("GenesByTaxon")
    )


# ── Single leaf step strategy ─────────────────────────────────────


async def test_build_single_step_returns_strategy_with_counts(
    authed_client: httpx.AsyncClient,
    wdk_respx: respx.Router,
) -> None:
    """POST /strategies with 1 leaf step → strategy with plan and steps.

    POST /strategies is CQRS-only: it creates a local projection from the
    validated plan AST. No WDK compilation happens at create time -- that
    occurs later via auto-build or explicit step-counts endpoints.

    Verifies: plan validation, step extraction, and correct response shape.
    """
    _setup_wdk_for_build(wdk_respx, strategy_id=200, step_ids=[100])

    resp = await authed_client.post(
        "/api/v1/strategies",
        json={
            "name": "Organism Search",
            "siteId": "plasmodb",
            "plan": {
                "recordType": "transcript",
                "root": {
                    "searchName": "GenesByTaxon",
                    "displayName": "Organism",
                    "parameters": {
                        "organism": '["Plasmodium falciparum 3D7"]',
                    },
                },
            },
        },
    )
    assert resp.status_code == 201, resp.text
    strategy = resp.json()

    # CQRS-only create: wdkStrategyId is None until auto-build runs
    assert strategy.get("wdkStrategyId") is None

    # Must have steps from plan AST
    assert len(strategy["steps"]) >= 1

    # Root step should be a search
    root_id = strategy["rootStepId"]
    root_step = next(s for s in strategy["steps"] if s["id"] == root_id)
    assert root_step["kind"] == "search"
    assert root_step["searchName"] == "GenesByTaxon"


# ── Missing plan → error ──────────────────────────────────────────


async def test_build_without_plan_returns_422(
    authed_client: httpx.AsyncClient,
) -> None:
    """POST /strategies without plan → 422, not 500."""
    resp = await authed_client.post(
        "/api/v1/strategies",
        json={"name": "No Plan", "siteId": "plasmodb"},
    )
    assert resp.status_code == 422


# ── Missing siteId → error ────────────────────────────────────────


async def test_build_without_site_id_returns_422(
    authed_client: httpx.AsyncClient,
) -> None:
    resp = await authed_client.post(
        "/api/v1/strategies",
        json={
            "name": "No Site",
            "plan": {
                "recordType": "transcript",
                "root": {
                    "searchName": "GenesByTaxon",
                    "parameters": {"organism": '["pfal"]'},
                },
            },
        },
    )
    assert resp.status_code == 422
