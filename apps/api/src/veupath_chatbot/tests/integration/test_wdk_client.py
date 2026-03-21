"""HTTP-level integration tests for VEuPathDBClient.

Uses ``respx`` to intercept outgoing ``httpx`` requests at the transport
layer so we validate real HTTP serialisation / deserialisation without
hitting the network.  No database or application fixtures are needed.

Run::

    pytest src/veupath_chatbot/tests/integration/test_wdk_client.py -v
"""

import json

import httpx
import pytest
import respx
from httpx import Response

from veupath_chatbot.integrations.veupathdb.client import (
    VEuPathDBClient,
    encode_context_param_values_for_wdk,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKSearch,
    WDKSearchResponse,
)
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.tests.fixtures.wdk_responses import (
    error_response_404,
    error_response_422,
    record_types_response,
    search_details_response,
    searches_response,
)

BASE = "https://plasmodb.org/plasmo/service"


@pytest.fixture
def client() -> VEuPathDBClient:
    """Standalone VEuPathDBClient pointing at a fake base URL."""
    return VEuPathDBClient(base_url=BASE, timeout=5.0)


# ------------------------------------------------------------------
# Happy-path tests
# ------------------------------------------------------------------


@respx.mock
async def test_get_record_types(client: VEuPathDBClient) -> None:
    """GET /record-types returns a parsed JSON list of record type strings."""
    expected = record_types_response()
    respx.get(f"{BASE}/record-types").mock(
        return_value=Response(200, json=expected),
    )

    result = await client.get_record_types()

    assert result == expected
    assert isinstance(result, list)
    assert len(result) == 6
    assert result[0] == "transcript"


@respx.mock
async def test_get_searches(client: VEuPathDBClient) -> None:
    """GET /record-types/gene/searches returns a list of search objects."""
    expected = searches_response()
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
    expected = search_details_response("GenesByTaxon")
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
    """POST refreshed-dependent-params sends encoded context body."""
    fake_response = {
        "organism": {
            "name": "organism",
            "displayName": "Organism",
            "vocabulary": [["Plasmodium falciparum 3D7", "P. falciparum 3D7"]],
        },
    }

    context = {
        "organism": ["Plasmodium falciparum 3D7"],
        "text_expression": "kinase",
    }

    route = respx.post(
        f"{BASE}/record-types/gene/searches/GenesByTaxon/refreshed-dependent-params",
    ).mock(return_value=Response(200, json=fake_response))

    result = await client.get_refreshed_dependent_params(
        "gene", "GenesByTaxon", "organism", context
    )

    assert route.called
    assert result == fake_response

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
    body = error_response_404()
    respx.get(f"{BASE}/record-types/nonexistent/searches").mock(
        return_value=Response(404, json=body),
    )

    with pytest.raises(WDKError) as exc_info:
        await client.get_searches("nonexistent")

    assert exc_info.value.status == 404


@respx.mock
async def test_http_422_raises_wdk_error(client: VEuPathDBClient) -> None:
    """A 422 response from WDK raises WDKError with status=422."""
    body = error_response_422()
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

    encoded = encode_context_param_values_for_wdk(context)

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
