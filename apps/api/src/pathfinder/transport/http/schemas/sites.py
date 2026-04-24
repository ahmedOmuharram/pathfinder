"""Sites request/response DTOs."""

from pydantic import ConfigDict, Field, JsonValue, RootModel

from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONArray, JSONObject


class SiteResponse(CamelModel):
    """VEuPathDB site information."""

    id: str
    name: str
    display_name: str
    base_url: str
    project_id: str
    is_portal: bool


class RecordTypeResponse(CamelModel):
    """Record type information."""

    name: str
    display_name: str
    description: str | None = None


class SearchResponse(CamelModel):
    """Search information."""

    name: str
    display_name: str
    description: str | None = None
    record_type: str


class DependentParamsRequest(CamelModel):
    """Dependent parameter values request."""

    parameter_name: str
    context_values: JSONObject = Field(default_factory=dict)


class SearchDetailsResponse(CamelModel):
    """Search details payload (UI-facing)."""

    search_data: JSONObject | None = Field(default=None)
    validation: JSONObject | None = None
    search_config: JSONObject | None = Field(default=None)
    parameters: JSONArray | None = None
    param_map: JSONObject | None = Field(default=None)
    question: JSONObject | None = None

    model_config = ConfigDict(extra="allow")

class DependentParamsResponse(RootModel[JSONArray]):
    """Dependent parameter values response."""

class SearchValidationRequest(CamelModel):
    """Search parameter validation request."""

    context_values: JSONObject = Field(default_factory=dict)


class ParamSpecsRequest(CamelModel):
    """Parameter specs request (optionally contextual)."""

    context_values: JSONObject = Field(default_factory=dict)


class ParamSpecResponse(CamelModel):
    """Normalized parameter spec (UI-friendly)."""

    name: str
    display_name: str | None = Field(default=None)
    type: str
    allow_empty_value: bool = Field(default=False)
    allow_multiple_values: bool | None = Field(default=None)
    multi_pick: bool | None = Field(default=None)
    min_selected_count: int | None = Field(default=None)
    max_selected_count: int | None = Field(default=None)
    count_only_leaves: bool = Field(default=False)
    initial_display_value: JsonValue | None = Field(default=None)
    vocabulary: JsonValue | None = None
    min: float | None = None
    max: float | None = None
    is_number: bool = Field(default=False)
    increment: float | None = None
    display_type: str | None = Field(default=None)
    is_visible: bool = Field(default=True)
    group: str | None = None
    dependent_params: list[str] = Field(default_factory=list)
    help: str | None = None
    # Filter-only metadata (populated only when type == "filter").
    ontology: list[JSONObject] | None = Field(default=None)
    filter_data_type_display_name: str | None = Field(default=None)
    # Dataset-only metadata (populated only when type == "input-dataset").
    parsers: list[JSONObject] | None = Field(default=None)
    default_id_list: str | None = Field(default=None)
    record_class_name: str | None = Field(default=None)

