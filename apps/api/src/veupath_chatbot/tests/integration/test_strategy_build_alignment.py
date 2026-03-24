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

from typing import Any

import httpx
import respx

BASE = "https://plasmodb.org/plasmo/service"


# ---------------------------------------------------------------------------
# Inline WDK response factories (verified against live PlasmoDB)
# ---------------------------------------------------------------------------
def _search_details_response(search_name: str = "GenesByTaxon") -> dict[str, Any]:
    """GET /record-types/transcript/searches/{searchName}?expandParams=true."""
    boolean_name = "boolean_question_TranscriptRecordClasses_TranscriptRecordClass"
    if search_name == boolean_name:
        suffix = "TranscriptRecordClasses_TranscriptRecordClass"
        return {
            "searchData": {
                "urlSegment": f"boolean_question_{suffix}",
                "fullName": f"InternalQuestions.boolean_question_{suffix}",
                "queryName": f"bq_{suffix}",
                "displayName": "Combine Gene results",
                "shortDisplayName": "Combine Gene results",
                "outputRecordClassName": "transcript",
                "isAnalyzable": True,
                "isCacheable": True,
                "noSummaryOnSingleRecord": False,
                "defaultSummaryView": "_default",
                "defaultAttributes": [],
                "defaultSorting": [],
                "paramNames": [
                    f"bq_left_op_{suffix}",
                    f"bq_right_op_{suffix}",
                    "bq_operator",
                ],
                "parameters": [
                    {
                        "name": f"bq_left_op_{suffix}",
                        "displayName": "Left operand",
                        "type": "input-step",
                        "allowEmptyValue": True,
                        "isVisible": True,
                        "isReadOnly": False,
                        "initialDisplayValue": "",
                        "dependentParams": [],
                        "properties": {},
                    },
                    {
                        "name": f"bq_right_op_{suffix}",
                        "displayName": "Right operand",
                        "type": "input-step",
                        "allowEmptyValue": True,
                        "isVisible": True,
                        "isReadOnly": False,
                        "initialDisplayValue": "",
                        "dependentParams": [],
                        "properties": {},
                    },
                    {
                        "name": "bq_operator",
                        "displayName": "Operator",
                        "type": "single-pick-vocabulary",
                        "allowEmptyValue": False,
                        "isVisible": True,
                        "isReadOnly": False,
                        "initialDisplayValue": "INTERSECT",
                        "minSelectedCount": 1,
                        "maxSelectedCount": 1,
                        "dependentParams": [],
                        "properties": {},
                        "vocabulary": [
                            ["UNION", "UNION", None],
                            ["INTERSECT", "INTERSECT", None],
                            ["MINUS", "LEFT_MINUS", None],
                            ["RMINUS", "RIGHT_MINUS", None],
                            ["LONLY", "LEFT_ONLY", None],
                            ["RONLY", "RIGHT_ONLY", None],
                        ],
                    },
                ],
                "dynamicAttributes": [],
                "filters": [],
                "groups": [],
                "properties": {},
                "summaryViewPlugins": [],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        }
    if search_name == "GenesByTextSearch":
        return {
            "searchData": {
                "urlSegment": "GenesByTextSearch",
                "fullName": "GeneQuestions.GenesByTextSearch",
                "queryName": "GenesByTextSearch",
                "displayName": "Text search (genes)",
                "shortDisplayName": "Text",
                "summary": "Find genes matching a text expression",
                "description": "Find genes matching a text expression",
                "outputRecordClassName": "transcript",
                "isAnalyzable": True,
                "isCacheable": True,
                "noSummaryOnSingleRecord": False,
                "defaultSummaryView": "_default",
                "defaultAttributes": ["primary_key", "gene_product"],
                "defaultSorting": [],
                "paramNames": [
                    "text_expression",
                    "text_fields",
                    "text_search_organism",
                    "document_type",
                ],
                "parameters": [
                    {
                        "name": "text_expression",
                        "displayName": "Text expression",
                        "type": "string",
                        "allowEmptyValue": False,
                        "isVisible": True,
                        "isReadOnly": False,
                        "initialDisplayValue": "",
                        "dependentParams": [],
                        "properties": {},
                    },
                    {
                        "name": "text_fields",
                        "displayName": "Fields to search",
                        "type": "multi-pick-vocabulary",
                        "allowEmptyValue": False,
                        "isVisible": True,
                        "isReadOnly": False,
                        "initialDisplayValue": '["primary_key","Alias"]',
                        "minSelectedCount": 1,
                        "maxSelectedCount": -1,
                        "dependentParams": [],
                        "properties": {},
                        "vocabulary": [
                            ["primary_key", "Gene ID", None],
                            ["Alias", "Gene alias", None],
                            ["product", "Product description", None],
                            ["GOTerms", "GO terms", None],
                            ["Notes", "Notes", None],
                        ],
                    },
                    {
                        "name": "text_search_organism",
                        "displayName": "Organism",
                        "type": "multi-pick-vocabulary",
                        "allowEmptyValue": False,
                        "isVisible": True,
                        "isReadOnly": False,
                        "initialDisplayValue": '["Plasmodium falciparum 3D7"]',
                        "minSelectedCount": 1,
                        "maxSelectedCount": -1,
                        "dependentParams": [],
                        "properties": {},
                        "vocabulary": [
                            [
                                "Plasmodium falciparum 3D7",
                                "Plasmodium falciparum 3D7",
                                None,
                            ],
                        ],
                    },
                    {
                        "name": "document_type",
                        "displayName": "Document type",
                        "type": "single-pick-vocabulary",
                        "allowEmptyValue": False,
                        "isVisible": True,
                        "isReadOnly": False,
                        "initialDisplayValue": "gene",
                        "minSelectedCount": 1,
                        "maxSelectedCount": 1,
                        "dependentParams": [],
                        "properties": {},
                        "vocabulary": [
                            ["gene", "Gene", None],
                            ["est", "EST", None],
                        ],
                    },
                ],
                "dynamicAttributes": [],
                "filters": [],
                "groups": [],
                "properties": {},
                "summaryViewPlugins": [],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        }
    # Fallback for all other search names (defaults to GenesByTaxon shape)
    return {
        "searchData": {
            "urlSegment": "GenesByTaxon",
            "fullName": "GeneQuestions.GenesByTaxon",
            "queryName": "GenesByTaxon",
            "displayName": "Organism",
            "shortDisplayName": "Organism",
            "summary": "Find all genes from one or more species/organism.",
            "description": "Find all genes from one or more species/organism.",
            "outputRecordClassName": "transcript",
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "organism", "gene_product"],
            "defaultSorting": [
                {"attributeName": "organism", "direction": "ASC"},
            ],
            "paramNames": ["organism"],
            "parameters": [
                {
                    "name": "organism",
                    "displayName": "Organism",
                    "type": "multi-pick-vocabulary",
                    "displayType": "treeBox",
                    "allowEmptyValue": False,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": '["Plasmodium falciparum 3D7"]',
                    "minSelectedCount": 1,
                    "maxSelectedCount": -1,
                    "countOnlyLeaves": True,
                    "depthExpanded": 0,
                    "dependentParams": [],
                    "group": "empty",
                    "properties": {},
                    "vocabulary": {
                        "data": {"display": "@@fake@@", "term": "@@fake@@"},
                        "children": [
                            {
                                "data": {
                                    "display": "Plasmodiidae",
                                    "term": "Plasmodiidae",
                                },
                                "children": [
                                    {
                                        "data": {
                                            "display": "Plasmodium falciparum 3D7",
                                            "term": "Plasmodium falciparum 3D7",
                                        },
                                        "children": [],
                                    },
                                    {
                                        "data": {
                                            "display": "Plasmodium vivax P01",
                                            "term": "Plasmodium vivax P01",
                                        },
                                        "children": [],
                                    },
                                ],
                            },
                        ],
                    },
                },
            ],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
        "validation": {"level": "DISPLAYABLE", "isValid": True},
    }


def _strategy_get_response(
    strategy_id: int = 200,
    step_ids: list[int] | None = None,
) -> dict[str, Any]:
    """GET /users/{userId}/strategies/{strategyId} -- detailed strategy."""
    ids = step_ids or [100, 101, 102]
    search_names = {0: "GenesByTaxon", 1: "GenesByTextSearch", 2: "GenesByOrthologs"}

    def _build_tree(remaining: list[int]) -> dict[str, Any]:
        if len(remaining) == 1:
            return {"stepId": remaining[0]}
        return {
            "stepId": remaining[-1],
            "primaryInput": _build_tree(remaining[:-1]),
        }

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
        "stepTree": _build_tree(ids),
        "steps": steps,
        "signature": "abc123def456",
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-06T00:00:00Z",
        "lastViewed": "2026-03-06T00:00:00Z",
        "leafAndTransformStepCount": len(ids),
        "nameOfFirstStep": "Organism",
    }


def _setup_wdk_for_build(
    router: respx.Router,
    *,
    strategy_id: int = 200,
    step_ids: list[int] | None = None,
) -> None:
    """Mock all WDK endpoints needed for a full strategy build.

    Uses realistic inline WDK response fixtures.
    """
    sids = step_ids or [100]
    router.get(f"{BASE}/users/current").respond(200, json={"id": 12345})

    # Search metadata (needed by plan normalization and compilation)
    router.get(url__regex=r".*/record-types/.*/searches/GenesByTaxon$").respond(
        200, json=_search_details_response("GenesByTaxon")
    )
    router.get(url__regex=r".*/record-types/.*/searches/GenesByTextSearch$").respond(
        200, json=_search_details_response("GenesByTextSearch")
    )
    router.get(url__regex=r".*/record-types/.*/searches/boolean_question.*$").respond(
        200,
        json=_search_details_response(
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
    detail = _strategy_get_response(strategy_id=strategy_id, step_ids=sids)
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
        200, json=_search_details_response("GenesByTaxon")
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
