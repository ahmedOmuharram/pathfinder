"""Pydantic models for WDK parameter types.

WDK parameters are discriminated on the ``type`` field.  The union type
``WDKParameter`` dispatches to the correct concrete class at parse time.

See Also
--------
wdk_models : Structural response models that reference ``WDKParameter``.
"""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from veupath_chatbot.integrations.veupathdb.wdk_models import WDKModel
from veupath_chatbot.platform.types import JSONObject, JSONValue


class WDKBaseParameter(WDKModel):
    """Common fields for all WDK parameter types."""

    name: str
    display_name: str = ""
    help: str | None = None
    type: str
    is_visible: bool = True
    group: str = ""
    is_read_only: bool = False
    allow_empty_value: bool = False
    visible_help: str | None = None
    visible_help_position: str | None = None
    dependent_params: list[str] = Field(default_factory=list)
    initial_display_value: str | None = None
    properties: dict[str, list[str]] = Field(default_factory=dict)


class WDKStringParam(WDKBaseParameter):
    """WDK string parameter."""

    type: Literal["string"] = "string"
    length: int = 0
    is_multi_line: bool = False
    is_number: bool = False


class WDKNumberParam(WDKBaseParameter):
    """WDK number parameter."""

    type: Literal["number"] = "number"
    min: float | None = None
    max: float | None = None
    increment: float | None = None


class WDKNumberRangeParam(WDKBaseParameter):
    """WDK number range parameter."""

    type: Literal["number-range"] = "number-range"
    min: float | None = None
    max: float | None = None
    increment: float | None = None


class WDKDateParam(WDKBaseParameter):
    """WDK date parameter."""

    type: Literal["date"] = "date"
    min_date: str | None = None
    max_date: str | None = None


class WDKDateRangeParam(WDKBaseParameter):
    """WDK date range parameter."""

    type: Literal["date-range"] = "date-range"
    min_date: str | None = None
    max_date: str | None = None


class WDKTimestampParam(WDKBaseParameter):
    """WDK timestamp parameter."""

    type: Literal["timestamp"] = "timestamp"


class WDKAnswerParam(WDKBaseParameter):
    """WDK answer/step-input parameter."""

    type: Literal["input-step"] = "input-step"


class WDKDatasetParam(WDKBaseParameter):
    """WDK dataset parameter."""

    type: Literal["input-dataset"] = "input-dataset"
    default_id_list: str | None = None
    record_class_name: str | None = None
    parsers: list[JSONObject] = Field(default_factory=list)


class WDKEnumParam(WDKBaseParameter):
    """WDK enum parameter (single-pick and multi-pick vocabulary).

    The secondary discriminator ``display_type`` determines the vocabulary
    shape and the corresponding wdk-client union member.
    """

    type: Literal["single-pick-vocabulary", "multi-pick-vocabulary"]
    display_type: str = ""
    max_selected_count: int | None = -1
    min_selected_count: int = 0
    vocabulary: JSONValue = None
    count_only_leaves: bool = False
    depth_expanded: int = 0


class WDKFilterParam(WDKBaseParameter):
    """WDK filter parameter."""

    type: Literal["filter"] = "filter"
    min_selected_count: int = 0
    ontology: list[JSONObject] = Field(default_factory=list)
    values: JSONObject | None = None
    filter_data_type_display_name: str | None = None
    hide_empty_ontology_nodes: bool = False
    sort_leaves_before_branches: bool = False
    count_predicts_answer_count: bool = False


WDKParameter = Annotated[
    WDKStringParam
    | WDKNumberParam
    | WDKNumberRangeParam
    | WDKDateParam
    | WDKDateRangeParam
    | WDKTimestampParam
    | WDKEnumParam
    | WDKFilterParam
    | WDKDatasetParam
    | WDKAnswerParam,
    Discriminator("type"),
]
"""Discriminated union of all WDK parameter types."""
