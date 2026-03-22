"""Pydantic models for WDK REST API responses.

Parsed at the integration boundary (VEuPathDBClient) so the service layer
receives typed, validated data instead of raw JSONObject dicts.  Models
use ``extra="ignore"`` for forward compatibility and ``frozen=True`` for
immutability.

Field names use snake_case in Python; ``alias_generator=to_camel`` maps
them to the camelCase keys in WDK JSON.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Discriminator, Field
from pydantic.alias_generators import to_camel

from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject, JSONValue


class WDKModel(CamelModel):
    """Base for all WDK REST API response models."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        frozen=True,
    )


class WDKFilterValue(WDKModel):
    """A single filter entry in SearchConfig."""

    name: str
    value: JSONValue = None
    disabled: bool = False


class WDKSearchConfig(WDKModel):
    """Search configuration: parameters + filters + weight."""

    parameters: dict[str, str] = Field(default_factory=dict)
    filters: list[WDKFilterValue] = Field(default_factory=list)
    view_filters: list[WDKFilterValue] = Field(default_factory=list)
    column_filters: JSONObject | None = None
    wdk_weight: int = 0


class WDKValidationErrors(WDKModel):
    """Validation error details."""

    general: list[str] = Field(default_factory=list)
    by_key: dict[str, list[str]] = Field(default_factory=dict)


class WDKValidation(WDKModel):
    """Step/search/strategy validation state."""

    level: str = "NONE"
    is_valid: bool = True
    errors: WDKValidationErrors | None = None


class WDKStepTree(WDKModel):
    """Recursive step tree structure."""

    step_id: int
    primary_input: WDKStepTree | None = None
    secondary_input: WDKStepTree | None = None


class WDKDisplayPreferences(WDKModel):
    """Step display preferences (column selection, sorting)."""

    column_selection: list[str] | None = None
    sort_columns: list[JSONObject] | None = None


class WDKStep(WDKModel):
    """A WDK step (search execution unit)."""

    id: int
    search_name: str
    search_config: WDKSearchConfig
    record_class_name: str | None = None
    validation: WDKValidation = Field(default_factory=WDKValidation)
    estimated_size: int | None = None
    strategy_id: int | None = None
    display_name: str = ""
    short_display_name: str = ""
    custom_name: str | None = None
    base_custom_name: str | None = None
    expanded: bool = False
    expanded_name: str | None = None
    is_filtered: bool = False
    description: str = ""
    owner_id: int = 0
    has_complete_step_analyses: bool = False
    display_preferences: WDKDisplayPreferences = Field(
        default_factory=WDKDisplayPreferences,
    )
    created_time: str = ""
    last_run_time: str = ""


class WDKStrategySummary(WDKModel):
    """Strategy summary (from list endpoint)."""

    strategy_id: int
    name: str
    root_step_id: int
    record_class_name: str | None = None
    signature: str = ""
    is_saved: bool = False
    is_valid: bool = True
    is_public: bool = False
    is_deleted: bool = False
    is_example: bool = False
    estimated_size: int | None = None
    description: str = ""
    author: str = ""
    organization: str = ""
    created_time: str = ""
    last_modified: str = ""
    last_viewed: str = ""
    release_version: str = ""
    name_of_first_step: str = ""
    leaf_and_transform_step_count: int = 0
    validation: WDKValidation | None = None


class WDKStrategyDetails(WDKStrategySummary):
    """Full strategy details (from detail endpoint)."""

    step_tree: WDKStepTree
    steps: dict[str, WDKStep] = Field(default_factory=dict)
    validation: WDKValidation | None = Field(default_factory=WDKValidation)


class WDKIdentifier(WDKModel):
    """Generic WDK ``{"id": <int>}`` response.

    Returned by POST endpoints that create a resource (strategy, step, etc.).
    """

    id: int


class WDKSortSpec(WDKModel):
    """Sorting specification."""

    attribute_name: str
    direction: str = "ASC"


class WDKParameterGroup(WDKModel):
    """Parameter group metadata."""

    name: str
    display_name: str = ""
    description: str = ""
    is_visible: bool = True
    display_type: str = ""
    parameters: list[str] = Field(default_factory=list)


class WDKSearch(WDKModel):
    """WDK search/question definition."""

    url_segment: str
    full_name: str = ""
    display_name: str = ""
    short_display_name: str = ""
    description: str = ""
    summary: str = ""
    output_record_class_name: str = ""
    is_analyzable: bool = False
    is_cacheable: bool = True
    param_names: list[str] = Field(default_factory=list)
    groups: list[WDKParameterGroup] = Field(default_factory=list)
    parameters: list[WDKParameter] | None = None
    default_attributes: list[str] = Field(default_factory=list)
    default_sorting: list[WDKSortSpec] = Field(default_factory=list)
    filters: list[JSONObject] = Field(default_factory=list)
    properties: dict[str, list[str]] = Field(default_factory=dict)
    allowed_primary_input_record_class_names: list[str] | None = None
    allowed_secondary_input_record_class_names: list[str] | None = None
    new_build: str = ""
    revise_build: str = ""
    query_name: str = ""
    no_summary_on_single_record: bool = False
    dynamic_attributes: list[JSONObject] = Field(default_factory=list)
    default_summary_view: str = "_default"
    summary_view_plugins: list[JSONObject] = Field(default_factory=list)
    icon_name: str | None = None
    help: str | None = None
    search_visible_help: str | None = None


class WDKSearchResponse(WDKModel):
    """Envelope for single-search detail endpoint."""

    search_data: WDKSearch
    validation: WDKValidation


class WDKRecordType(WDKModel):
    """WDK record type metadata.

    The expanded single record type endpoint (``GET /record-types/{type}?format=expanded``)
    includes ``attributes`` as a list of attribute field objects.  Some WDK
    deployments return ``attributesMap`` (a dict keyed by attribute name) instead.
    Both are modelled as optional ``JSONValue`` so callers can pass either format
    through to ``build_attribute_list`` / ``extract_detail_attributes``.
    """

    url_segment: str
    full_name: str = ""
    display_name: str = ""
    display_name_plural: str = ""
    short_display_name: str = ""
    description: str = ""
    record_id_attribute_name: str = ""
    primary_key_column_refs: list[str] = Field(default_factory=list)
    use_basket: bool = False
    has_all_records_query: bool = False
    properties: dict[str, list[str]] = Field(default_factory=dict)
    searches: list[WDKSearch] | None = None
    icon_name: str | None = None
    attributes: JSONValue = None
    attributes_map: JSONValue = None


class WDKAnswerMeta(WDKModel):
    """Answer/report metadata with counts."""

    total_count: int = 0
    response_count: int = 0
    display_total_count: int = 0
    view_total_count: int = 0
    display_view_total_count: int = 0
    record_class_name: str = ""
    attributes: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)


class WDKAnswer(WDKModel):
    """WDK answer/report response."""

    meta: WDKAnswerMeta
    records: list[JSONObject] = Field(default_factory=list)


class WDKStepAnalysisType(WDKModel):
    """Step analysis type definition (from ``GET .../step-analyses/types``)."""

    name: str
    display_name: str
    short_description: str = ""
    description: str = ""
    release_version: str = ""
    custom_thumbnail: str | None = None
    param_names: list[str] = Field(default_factory=list)
    groups: list[WDKParameterGroup] = Field(default_factory=list)


class WDKStepAnalysisConfig(WDKModel):
    """Step analysis instance configuration."""

    analysis_id: int
    step_id: int
    analysis_name: str
    display_name: str = ""
    short_description: str | None = None
    description: str | None = None
    user_notes: str | None = None
    status: str = ""
    parameters: dict[str, str] = Field(default_factory=dict)
    validation: WDKValidation | None = None


class WDKUserInfo(WDKModel):
    """WDK user profile (from ``GET /users/current``)."""

    id: int
    email: str | None = None
    is_guest: bool = True
    properties: dict[str, str] = Field(default_factory=dict)


class WDKRecordInstance(WDKModel):
    """A single record from a WDK answer/report."""

    display_name: str = ""
    id: list[dict[str, str]] = Field(default_factory=list)
    record_class_name: str = ""
    attributes: dict[str, JSONValue] = Field(default_factory=dict)
    tables: dict[str, JSONValue] = Field(default_factory=dict)
    table_errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# WDKDatasetConfig — discriminated union (5 source types)
# ---------------------------------------------------------------------------

class WDKDatasetIdListContent(WDKModel):
    """Content for ``sourceType: "idList"``."""

    ids: list[str]


class WDKDatasetBasketContent(WDKModel):
    """Content for ``sourceType: "basket"``."""

    basket_name: str


class WDKDatasetFileContent(WDKModel):
    """Content for ``sourceType: "file"``."""

    temporary_file_id: str
    parser: str
    search_name: str
    parameter_name: str


class WDKDatasetStrategyContent(WDKModel):
    """Content for ``sourceType: "strategy"``."""

    strategy_id: int


class WDKDatasetUrlContent(WDKModel):
    """Content for ``sourceType: "url"``."""

    url: str
    parser: str
    search_name: str
    parameter_name: str


class WDKDatasetConfigIdList(WDKModel):
    """Dataset config with id-list source."""

    source_type: Literal["idList"]
    source_content: WDKDatasetIdListContent


class WDKDatasetConfigBasket(WDKModel):
    """Dataset config with basket source."""

    source_type: Literal["basket"]
    source_content: WDKDatasetBasketContent


class WDKDatasetConfigFile(WDKModel):
    """Dataset config with file source."""

    source_type: Literal["file"]
    source_content: WDKDatasetFileContent


class WDKDatasetConfigStrategy(WDKModel):
    """Dataset config with strategy source."""

    source_type: Literal["strategy"]
    source_content: WDKDatasetStrategyContent


class WDKDatasetConfigUrl(WDKModel):
    """Dataset config with URL source."""

    source_type: Literal["url"]
    source_content: WDKDatasetUrlContent


WDKDatasetConfig = Annotated[
    WDKDatasetConfigIdList
    | WDKDatasetConfigBasket
    | WDKDatasetConfigFile
    | WDKDatasetConfigStrategy
    | WDKDatasetConfigUrl,
    Discriminator("source_type"),
]
"""Discriminated union of WDK dataset config source types."""


# Resolve forward reference: WDKSearch.parameters uses WDKParameter
from veupath_chatbot.integrations.veupathdb.wdk_parameters import WDKParameter  # noqa: E402, I001

WDKSearch.model_rebuild()
WDKSearchResponse.model_rebuild()
WDKRecordType.model_rebuild()
