from __future__ import annotations

import pytest

from pathfinder.domain.parameters.values import MultiPickValue, StringValue
from pathfinder.domain.search import SearchContext
from pathfinder.platform.errors import ValidationError
from pathfinder.services.catalog.param_validation import validate_parameters
from pathfinder.services.catalog.validation_callbacks import make_validation_callbacks

pytestmark = [pytest.mark.live_wdk, pytest.mark.asyncio]

_ORGANISM = "Plasmodium falciparum 3D7"


async def test_valid_params_canonicalize_against_real_spec(wdk_session: None) -> None:
    del wdk_session
    ctx = SearchContext(
        site_id="plasmodb", record_type="transcript", search_name="GenesByTaxon"
    )
    canonical = await validate_parameters(
        ctx,
        parameters={"organism": MultiPickValue(values=[_ORGANISM])},
        callbacks=make_validation_callbacks("plasmodb"),
    )
    organism = canonical["organism"]
    assert isinstance(organism, MultiPickValue)
    assert _ORGANISM in organism.values


async def test_unknown_search_raises(wdk_session: None) -> None:
    del wdk_session
    ctx = SearchContext(
        site_id="plasmodb", record_type="transcript", search_name="NotARealSearch"
    )
    with pytest.raises(ValidationError):
        await validate_parameters(
            ctx,
            parameters={"organism": MultiPickValue(values=[_ORGANISM])},
            callbacks=make_validation_callbacks("plasmodb"),
        )


async def test_unknown_param_key_raises(wdk_session: None) -> None:
    del wdk_session
    ctx = SearchContext(
        site_id="plasmodb", record_type="transcript", search_name="GenesByTaxon"
    )
    with pytest.raises(ValidationError):
        await validate_parameters(
            ctx,
            parameters={
                "organism": MultiPickValue(values=[_ORGANISM]),
                "not_a_real_param": StringValue(value="x"),
            },
            callbacks=make_validation_callbacks("plasmodb"),
        )
