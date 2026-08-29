"""What the EDA routes promise: a response omits no field, a request may."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from pathfinder.transport.http.schemas.eda import (
    ConversationEdaResponse,
    EdaAnalysisPatchResponse,
    EdaCountRequest,
    EdaCountResponse,
    EdaDistributionRequest,
    EdaEntityResponse,
    EdaJobRefResponse,
    EdaStudyDetailResponse,
    EdaStudyListResponse,
    EdaStudySummaryResponse,
    EdaVariableResponse,
    EdaVizPointResponse,
    EdaVizRequest,
    EdaVizResponse,
)

_RESPONSES = [
    ConversationEdaResponse,
    EdaAnalysisPatchResponse,
    EdaCountResponse,
    EdaEntityResponse,
    EdaJobRefResponse,
    EdaStudyDetailResponse,
    EdaStudyListResponse,
    EdaStudySummaryResponse,
    EdaVariableResponse,
    EdaVizPointResponse,
    EdaVizResponse,
]

# One optional input per request model, so a client may omit it.
_OPTIONAL_INPUTS = {
    EdaCountRequest: {"filters"},
    EdaDistributionRequest: {"filters"},
    EdaVizRequest: {
        "effectSizeThreshold",
        "significanceThreshold",
        "effectDirection",
    },
}


@pytest.mark.parametrize("model", _RESPONSES, ids=lambda m: m.__name__)
def test_a_response_model_requires_every_field_it_declares(
    model: type[BaseModel],
) -> None:
    """The builder fills every field, so a consumer never defaults one."""
    schema = model.model_json_schema(by_alias=True)
    assert schema["required"] == list(schema["properties"])


@pytest.mark.parametrize(
    ("model", "optional"),
    _OPTIONAL_INPUTS.items(),
    ids=lambda value: getattr(value, "__name__", ""),
)
def test_a_request_model_keeps_the_inputs_a_client_may_omit(
    model: type[BaseModel],
    optional: set[str],
) -> None:
    schema = model.model_json_schema(by_alias=True)
    assert set(schema["properties"]) - set(schema["required"]) == optional


def test_a_point_may_carry_no_p_value_and_still_names_the_key() -> None:
    schema = EdaVizPointResponse.model_json_schema(by_alias=True)
    assert schema["properties"]["pValue"]["anyOf"] == [
        {"type": "number"},
        {"type": "null"},
    ]
    assert "pValue" in schema["required"]
