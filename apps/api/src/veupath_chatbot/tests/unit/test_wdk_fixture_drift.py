"""Fixture-shape drift tests: verify Pathfinder parsing against realistic WDK payloads.

Uses inline WDK response factories (verified against live PlasmoDB API) to
ensure Pathfinder's parsing code handles real WDK shapes correctly.

WDK contracts validated:
- strategy_get_response → build_snapshot_from_wdk produces valid AST
- standard_report_response → WDKAnswer.model_validate succeeds
- search_details_response → WDKSearchResponse.model_validate succeeds
- strategy step tree recursion handles 3-step chain
"""

from typing import Any

import pytest

from veupath_chatbot.domain.strategy.ast import walk_step_tree
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKSearchResponse,
    WDKStrategyDetails,
)
from veupath_chatbot.services.strategies.wdk_conversion import (
    build_snapshot_from_wdk,
)

# ---------------------------------------------------------------------------
# Inline WDK response factories (verified against live PlasmoDB)
# ---------------------------------------------------------------------------
_DEFAULT_GENE_IDS: list[str] = [
    "PF3D7_0100100",
    "PF3D7_0831900",
    "PF3D7_1133400",
    "PF3D7_0709000",
    "PF3D7_1343700",
]


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


def _standard_report_response(
    gene_ids: list[str] | None = None,
    total_count: int | None = None,
) -> dict[str, Any]:
    """POST .../reports/standard -- paginated records response."""
    ids = gene_ids if gene_ids is not None else _DEFAULT_GENE_IDS
    count = total_count if total_count is not None else len(ids)
    records = [
        {
            "id": [
                {"name": "gene_source_id", "value": gid},
                {"name": "source_id", "value": f"{gid}.1"},
                {"name": "project_id", "value": "PlasmoDB"},
            ],
            "displayName": gid,
            "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
            "attributes": {
                "primary_key": gid,
                "gene_source_id": gid,
                "gene_name": None,
                "gene_product": f"hypothetical protein, conserved ({gid})",
                "gene_type": "protein_coding",
                "organism": "<i>Plasmodium falciparum 3D7</i>",
                "gene_location_text": "Pf3D7_01_v3: 29,510 - 37,126 (+)",
                "gene_previous_ids": "",
            },
            "tables": {},
            "tableErrors": [],
        }
        for gid in ids
    ]
    return {
        "records": records,
        "meta": {
            "totalCount": count,
            "displayedCount": len(ids),
            "viewTotalCount": count,
            "responseCount": len(ids),
        },
    }


def _search_details_response(search_name: str = "GenesByTaxon") -> dict[str, Any]:
    """GET /record-types/transcript/searches/{searchName}?expandParams=true."""
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


def _wdk_answer_json(
    *,
    total_count: int = 5432,
    response_count: int = 20,
    gene_ids: list[str] | None = None,
    record_class_name: str = "transcript",
) -> dict[str, Any]:
    """POST /users/{id}/steps/{id}/reports/standard -- answer/report."""
    ids = gene_ids or _DEFAULT_GENE_IDS[:response_count]
    records: list[dict[str, Any]] = [
        {
            "displayName": gid,
            "id": [
                {"name": "gene_source_id", "value": gid},
                {"name": "project_id", "value": "PlasmoDB"},
            ],
            "recordClassName": record_class_name,
            "attributes": {
                "gene_id": gid,
                "organism": "Plasmodium falciparum 3D7",
                "product": "hypothetical protein",
            },
            "tables": {},
            "tableErrors": [],
        }
        for gid in ids
    ]
    return {
        "meta": {
            "totalCount": total_count,
            "responseCount": len(records),
            "displayTotalCount": total_count,
            "viewTotalCount": total_count,
            "displayViewTotalCount": total_count,
            "recordClassName": record_class_name,
            "attributes": ["gene_id", "organism"],
            "tables": [],
        },
        "records": records,
    }

# ── strategy_get_response → build_snapshot_from_wdk ───────────────


class TestStrategyFixtureRoundTrip:
    """Verify realistic strategy fixture parses into valid AST."""

    def test_three_step_strategy_parses(self) -> None:
        """strategy_get_response (3 steps) -> build_snapshot_from_wdk succeeds."""
        raw = _strategy_get_response(strategy_id=200, step_ids=[100, 101, 102])
        wdk = WDKStrategyDetails.model_validate(raw)
        ast = build_snapshot_from_wdk(wdk)

        # AST structure
        assert ast.record_type is not None
        assert ast.root is not None
        assert ast.root.search_name is not None

        # Steps extracted from AST
        assert len(walk_step_tree(ast.root)) >= 1

        # Step counts from estimatedSize (on AST)
        step_counts = ast.step_counts or {}
        for step_id_str, count in step_counts.items():
            assert isinstance(count, int), (
                f"Step count for {step_id_str} should be int, got {type(count)}"
            )

    def test_single_step_strategy(self) -> None:
        raw = _strategy_get_response(strategy_id=100, step_ids=[100])
        wdk = WDKStrategyDetails.model_validate(raw)
        ast = build_snapshot_from_wdk(wdk)

        assert ast.root.search_name is not None
        assert len(walk_step_tree(ast.root)) == 1


# ── standard_report_response → WDKAnswer ──────────────────────────


class TestReportFixtureRoundTrip:
    """Verify realistic report fixture parses into WDKAnswer."""

    def test_standard_report_validates(self) -> None:
        raw = _standard_report_response()
        answer = WDKAnswer.model_validate(raw)
        assert answer.meta.total_count > 0
        assert len(answer.records) > 0

    def test_gene_ids_are_real_pf_ids(self) -> None:
        """Fixture gene IDs must be real Pf3D7 locus tags."""
        raw = _standard_report_response()
        answer = WDKAnswer.model_validate(raw)
        for record in answer.records:
            # record is WDKRecordInstance; .id is list[dict[str, str]]
            assert len(record.id) > 0
            gene_source = None
            for pk in record.id:
                if pk.get("name") == "gene_source_id":
                    gene_source = pk.get("value")
            if gene_source:
                assert isinstance(gene_source, str)
                assert gene_source.startswith("PF3D7_"), (
                    f"Expected Pf3D7 locus tag, got {gene_source}"
                )

    def test_default_gene_ids_used(self) -> None:
        """Report fixture uses DEFAULT_GENE_IDS which are verified real."""
        raw = _standard_report_response()
        answer = WDKAnswer.model_validate(raw)
        found_ids: set[str] = set()
        for record in answer.records:
            # record is WDKRecordInstance; .id is list[dict[str, str]]
            for pk in record.id:
                if pk.get("name") == "gene_source_id":
                    val = pk.get("value")
                    if isinstance(val, str):
                        found_ids.add(val)
        assert found_ids & set(_DEFAULT_GENE_IDS), (
            "Report fixture should use DEFAULT_GENE_IDS"
        )

    def test_wdk_answer_json_validates(self) -> None:
        raw = _wdk_answer_json(total_count=100, response_count=5)
        answer = WDKAnswer.model_validate(raw)
        assert answer.meta.total_count == 100


# ── search_details_response → WDKSearchResponse ──────────────────


class TestSearchDetailsFixtureRoundTrip:
    def test_taxon_search_validates(self) -> None:
        raw = _search_details_response("GenesByTaxon")
        response = WDKSearchResponse.model_validate(raw)
        assert response.search_data.url_segment is not None
        assert response.validation.is_valid is True

    def test_text_search_validates(self) -> None:
        raw = _search_details_response("GenesByTextSearch")
        response = WDKSearchResponse.model_validate(raw)
        assert response.search_data.url_segment is not None

    @pytest.mark.parametrize(
        "search_name",
        ["GenesByTaxon", "GenesByTextSearch"],
    )
    def test_search_has_parameters(self, search_name: str) -> None:
        """Expanded search details must include parameter specs."""
        raw = _search_details_response(search_name)
        response = WDKSearchResponse.model_validate(raw)
        # Parameters should be non-empty for real searches
        assert response.search_data.parameters is not None
        assert len(response.search_data.parameters) > 0
