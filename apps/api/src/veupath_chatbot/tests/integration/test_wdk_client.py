"""HTTP-level integration tests for VEuPathDBClient.

Uses ``respx`` to intercept outgoing ``httpx`` requests at the transport
layer so we validate real HTTP serialisation / deserialisation without
hitting the network.  No database or application fixtures are needed.

Run::

    pytest src/veupath_chatbot/tests/integration/test_wdk_client.py -v
"""

import json
from typing import Any

import httpx
import pytest
import respx
from httpx import Response

from veupath_chatbot.integrations.veupathdb.client import (
    VEuPathDBClient,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKRecordType,
    WDKSearch,
    WDKSearchResponse,
    encode_wdk_params,
)
from veupath_chatbot.platform.errors import WDKError

BASE = "https://plasmodb.org/plasmo/service"


# ---------------------------------------------------------------------------
# Inline test data (previously from wdk_responses.py)
# ---------------------------------------------------------------------------


def _record_types_response() -> list[str]:
    return [
        "transcript",
        "gene",
        "organism",
        "popsetSequence",
        "sample",
        "genomic-sequence",
    ]


def _searches_response() -> list[dict[str, Any]]:
    return [
        {
            "urlSegment": "GenesByTaxon",
            "fullName": "GeneQuestions.GenesByTaxon",
            "queryName": "GenesByTaxon",
            "displayName": "Organism",
            "shortDisplayName": "Organism",
            "outputRecordClassName": "transcript",
            "paramNames": ["organism"],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "organism", "gene_product"],
            "defaultSorting": [
                {"attributeName": "organism", "direction": "ASC"},
            ],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
        {
            "urlSegment": "GenesByTextSearch",
            "fullName": "GeneQuestions.GenesByTextSearch",
            "queryName": "GenesByTextSearch",
            "displayName": "Text search (genes)",
            "shortDisplayName": "Text",
            "outputRecordClassName": "transcript",
            "paramNames": [
                "text_expression",
                "text_fields",
                "text_search_organism",
                "document_type",
            ],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "gene_product"],
            "defaultSorting": [],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
        {
            "urlSegment": "boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
            "fullName": "InternalQuestions.boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
            "queryName": "bq_TranscriptRecordClasses_TranscriptRecordClass",
            "displayName": "Combine Gene results",
            "shortDisplayName": "Combine Gene results",
            "outputRecordClassName": "transcript",
            "paramNames": [
                "bq_left_op_TranscriptRecordClasses_TranscriptRecordClass",
                "bq_right_op_TranscriptRecordClasses_TranscriptRecordClass",
                "bq_operator",
            ],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": [],
            "defaultSorting": [],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
            "allowedPrimaryInputRecordClassNames": ["transcript"],
            "allowedSecondaryInputRecordClassNames": ["transcript"],
        },
        {
            "urlSegment": "GenesByOrthologs",
            "fullName": "GeneQuestions.GenesByOrthologs",
            "queryName": "GenesByOrthologs",
            "displayName": "Orthologs",
            "shortDisplayName": "Orthologs",
            "description": "Find genes by ortholog transform",
            "outputRecordClassName": "transcript",
            "paramNames": ["inputStepId", "organism", "isSyntenic"],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "gene_product"],
            "defaultSorting": [],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
    ]


def _search_details_response() -> dict[str, Any]:
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
                        "data": {
                            "display": "@@fake@@",
                            "term": "@@fake@@",
                        },
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
        "validation": {
            "level": "DISPLAYABLE",
            "isValid": True,
        },
    }


@pytest.fixture
def client() -> VEuPathDBClient:
    """Standalone VEuPathDBClient pointing at a fake base URL."""
    return VEuPathDBClient(base_url=BASE, timeout=5.0)


# ------------------------------------------------------------------
# Happy-path tests
# ------------------------------------------------------------------


@respx.mock
async def test_get_record_types(client: VEuPathDBClient) -> None:
    """GET /record-types returns a list of WDKRecordType models."""
    expected = _record_types_response()
    respx.get(f"{BASE}/record-types").mock(
        return_value=Response(200, json=expected),
    )

    result = await client.get_record_types()

    assert isinstance(result, list)
    assert len(result) == 6
    assert all(isinstance(rt, WDKRecordType) for rt in result)
    assert result[0].url_segment == "transcript"


@respx.mock
async def test_get_searches(client: VEuPathDBClient) -> None:
    """GET /record-types/gene/searches returns a list of search objects."""
    expected = _searches_response()
    respx.get(f"{BASE}/record-types/gene/searches").mock(
        return_value=Response(200, json=expected),
    )

    result = await client.get_searches("gene")

    assert len(result) == 4
    assert all(isinstance(s, WDKSearch) for s in result)
    assert any(s.url_segment == "GenesByTaxon" for s in result)


@respx.mock
async def test_get_search_details(client: VEuPathDBClient) -> None:
    """GET /record-types/transcript/searches/GenesByTaxon?expandParams=true returns details."""
    expected = _search_details_response()
    route = respx.get(
        f"{BASE}/record-types/transcript/searches/GenesByTaxon",
        params={"expandParams": "true"},
    ).mock(return_value=Response(200, json=expected))

    result = await client.get_search_details("transcript", "GenesByTaxon")

    assert route.called
    assert isinstance(result, WDKSearchResponse)
    assert result.search_data is not None
    assert result.validation is not None
    assert result.search_data.url_segment == "GenesByTaxon"
    assert result.search_data.parameters is not None


@respx.mock
async def test_get_refreshed_dependent_params(client: VEuPathDBClient) -> None:
    """POST refreshed-dependent-params sends encoded context body.

    WDK returns a JSON array of parameter objects.  The client now
    parses each item via the WDKParameter discriminated union.
    """
    fake_response = [
        {
            "name": "organism",
            "displayName": "Organism",
            "type": "single-pick-vocabulary",
            "vocabulary": [["Plasmodium falciparum 3D7", "P. falciparum 3D7"]],
        },
    ]

    context = encode_wdk_params(
        {
            "organism": ["Plasmodium falciparum 3D7"],
            "text_expression": "kinase",
        }
    )

    route = respx.post(
        f"{BASE}/record-types/gene/searches/GenesByTaxon/refreshed-dependent-params",
    ).mock(return_value=Response(200, json=fake_response))

    result = await client.get_refreshed_dependent_params(
        "gene", "GenesByTaxon", "organism", context
    )

    assert route.called
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].name == "organism"

    # Verify the request body was properly encoded
    sent_body = json.loads(route.calls.last.request.content)
    assert sent_body["changedParam"]["name"] == "organism"
    # Multi-pick arrays should be JSON-encoded strings, not raw arrays
    ctx_values = sent_body["contextParamValues"]
    assert ctx_values["organism"] == json.dumps(["Plasmodium falciparum 3D7"])
    assert ctx_values["text_expression"] == "kinase"


# ------------------------------------------------------------------
# Error handling tests
# ------------------------------------------------------------------


@respx.mock
async def test_http_404_raises_wdk_error(client: VEuPathDBClient) -> None:
    """A 404 response from WDK raises WDKError with status=404."""
    body = {
        "status": "not_found",
        "message": "Step 99999 not found for user 12345",
    }
    respx.get(f"{BASE}/record-types/nonexistent/searches").mock(
        return_value=Response(404, json=body),
    )

    with pytest.raises(WDKError) as exc_info:
        await client.get_searches("nonexistent")

    assert exc_info.value.status == 404


@respx.mock
async def test_http_422_raises_wdk_error(client: VEuPathDBClient) -> None:
    """A 422 response from WDK raises WDKError with status=422."""
    body = {
        "status": "unprocessable_entity",
        "message": "Validation failed",
        "errors": {
            "general": [],
            "byKey": {
                "organism": [
                    "Required parameter 'organism' is missing or empty.",
                ],
            },
        },
    }
    respx.get(
        f"{BASE}/record-types/gene/searches/GenesByTaxon",
        params={"expandParams": "true"},
    ).mock(return_value=Response(422, json=body))

    with pytest.raises(WDKError) as exc_info:
        await client.get_search_details("gene", "GenesByTaxon")

    assert exc_info.value.status == 422


@respx.mock
async def test_http_500_raises_wdk_error(client: VEuPathDBClient) -> None:
    """A 500 response from WDK raises WDKError with status=500."""
    respx.get(f"{BASE}/record-types").mock(
        return_value=Response(500, json={"error": "internal server error"}),
    )

    with pytest.raises(WDKError) as exc_info:
        await client.get_record_types()

    assert exc_info.value.status == 500


# ------------------------------------------------------------------
# Retry behaviour
# ------------------------------------------------------------------


@respx.mock
async def test_transport_error_raises_wdk_error(client: VEuPathDBClient) -> None:
    """TransportError (e.g. connection refused) raises WDKError with 502 status."""
    respx.get(f"{BASE}/record-types").mock(
        side_effect=httpx.ConnectError("connection refused"),
    )

    with pytest.raises(WDKError) as exc_info:
        await client.get_record_types()

    assert exc_info.value.status == 502


# ------------------------------------------------------------------
# Utility function tests
# ------------------------------------------------------------------


def test_context_param_encoding() -> None:
    """Multi-pick arrays become JSON strings; scalars pass through."""
    context = {
        "organism": ["Plasmodium falciparum 3D7", "Plasmodium vivax P01"],
        "text_expression": "kinase",
        "threshold": 42,
        "nested": {"a": 1, "b": 2},
        "empty": None,
    }

    encoded = encode_wdk_params(context)

    # Lists become JSON-encoded strings
    assert (
        encoded["organism"] == '["Plasmodium falciparum 3D7", "Plasmodium vivax P01"]'
    )
    # Strings pass through unchanged
    assert encoded["text_expression"] == "kinase"
    # Non-string scalars become str()
    assert encoded["threshold"] == "42"
    # Dicts become JSON-encoded strings
    assert encoded["nested"] == '{"a": 1, "b": 2}'
    # None values are skipped entirely
    assert "empty" not in encoded
