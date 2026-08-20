from __future__ import annotations

import pytest

from pathfinder.domain.parameters.specs import find_missing_required_params
from pathfinder.domain.parameters.values import MultiPickValue, StringValue
from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.factory import get_wdk_client
from pathfinder.integrations.veupathdb.wdk_models import WDKSearchResponse
from pathfinder.platform.errors import ValidationError
from pathfinder.services.catalog.param_adapters import adapt_param_specs_from_search
from pathfinder.services.catalog.param_validation import validate_parameters
from pathfinder.services.catalog.validation_callbacks import make_validation_callbacks

pytestmark = [pytest.mark.live_wdk, pytest.mark.asyncio]


async def _fetch_response() -> WDKSearchResponse:
    client = get_wdk_client("plasmodb")
    return await client.get_search_details_with_params(
        "transcript", "GenesByText", context={}
    )


async def test_layer1_wdk_parse_preserves_allow_empty_false(
    wdk_session: None,
) -> None:
    del wdk_session
    response = await _fetch_response()
    params = {p.name: p for p in (response.search_data.parameters or [])}
    assert params["text_expression"].allow_empty_value is False


async def test_layer2_adapter_preserves_allow_empty_false(
    wdk_session: None,
) -> None:
    del wdk_session
    response = await _fetch_response()
    specs = adapt_param_specs_from_search(response.search_data)
    assert specs["text_expression"].allow_empty_value is False


async def test_layer3_find_missing_flags_absent_required(
    wdk_session: None,
) -> None:
    del wdk_session
    response = await _fetch_response()
    specs = adapt_param_specs_from_search(response.search_data)
    assert "text_expression" in find_missing_required_params(specs, {})


async def test_layer4_validate_parameters_raises_on_empty(
    wdk_session: None,
) -> None:
    del wdk_session
    with pytest.raises(ValidationError) as raised:
        await validate_parameters(
            SearchContext("plasmodb", "transcript", "GenesByText"),
            parameters={},
            callbacks=make_validation_callbacks("plasmodb"),
        )

    # The refusal names the empty required parameter, whatever wording WDK
    # or the local check gives it.
    assert "text_expression" in str(raised.value)


async def test_document_type_is_hidden_required_with_fixed_default(
    wdk_session: None,
) -> None:
    del wdk_session
    response = await _fetch_response()
    specs = adapt_param_specs_from_search(response.search_data)
    doc = specs["document_type"]
    assert doc.is_visible is False
    assert doc.allow_empty_value is False
    assert doc.initial_display_value == "gene"


async def test_validate_parameters_autofills_hidden_document_type(
    wdk_session: None,
) -> None:
    # The model supplies only the VISIBLE required params (it can't see the
    # hidden document_type). validate_parameters must auto-fill document_type
    # rather than reject — the contradiction that spiralled create_plan.
    del wdk_session
    result = await validate_parameters(
        SearchContext("plasmodb", "transcript", "GenesByText"),
        parameters={
            "text_expression": StringValue(value="kinase"),
            "text_fields": MultiPickValue(values=["product"]),
            "text_search_organism": MultiPickValue(
                values=["Plasmodium falciparum 3D7"]
            ),
        },
        callbacks=make_validation_callbacks("plasmodb"),
    )
    assert "document_type" in result.params
    assert result.params["document_type"].to_decoded() == "gene"
    # The caller never stated it, so the walk discloses it.
    assert "document_type" in result.substituted
