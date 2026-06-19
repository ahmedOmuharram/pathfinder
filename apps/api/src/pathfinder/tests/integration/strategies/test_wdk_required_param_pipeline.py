from __future__ import annotations

import pytest

from pathfinder.domain.parameters.specs import find_missing_required_params
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
    require_wdk_creds: None,
    wdk_session: None,
) -> None:
    del require_wdk_creds, wdk_session
    response = await _fetch_response()
    params = {p.name: p for p in (response.search_data.parameters or [])}
    assert params["text_expression"].allow_empty_value is False


async def test_layer2_adapter_preserves_allow_empty_false(
    require_wdk_creds: None,
    wdk_session: None,
) -> None:
    del require_wdk_creds, wdk_session
    response = await _fetch_response()
    specs = adapt_param_specs_from_search(response.search_data)
    assert specs["text_expression"].allow_empty_value is False


async def test_layer3_find_missing_flags_absent_required(
    require_wdk_creds: None,
    wdk_session: None,
) -> None:
    del require_wdk_creds, wdk_session
    response = await _fetch_response()
    specs = adapt_param_specs_from_search(response.search_data)
    assert "text_expression" in find_missing_required_params(specs, {})


async def test_layer4_validate_parameters_raises_on_empty(
    require_wdk_creds: None,
    wdk_session: None,
) -> None:
    del require_wdk_creds, wdk_session
    with pytest.raises(ValidationError, match=r"[Mm]issing required"):
        await validate_parameters(
            SearchContext("plasmodb", "transcript", "GenesByText"),
            parameters={},
            callbacks=make_validation_callbacks("plasmodb"),
        )
