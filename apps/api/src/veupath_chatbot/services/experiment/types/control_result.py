"""Control-test result types.

Typed representation of the dict returned by
``run_positive_negative_controls()`` and ``run_controls_against_tree()``.
Replaces the untyped ``JSONObject`` that required ``safe_int()`` for
field extraction.
"""

from pydantic import Field

from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject


class ControlTargetData(CamelModel):
    """Target step info in a control-test result."""

    search_name: str = ""
    parameters: JSONObject = Field(default_factory=dict)
    step_id: int | None = None
    result_count: int | None = None


class ControlSetData(CamelModel):
    """One control set (positive or negative) in a control-test result."""

    controls_count: int = 0
    intersection_count: int = 0
    intersection_ids: list[str] = Field(default_factory=list)
    intersection_ids_sample: list[str] = Field(default_factory=list)
    target_step_id: int | None = None
    target_result_count: int = 0
    missing_ids_sample: list[str] = Field(default_factory=list)
    unexpected_hits_sample: list[str] = Field(default_factory=list)
    recall: float | None = None
    false_positive_rate: float | None = None


class ControlTestResult(CamelModel):
    """Full control-test result (positive + negative intersection data)."""

    site_id: str = ""
    record_type: str = ""
    target: ControlTargetData = Field(default_factory=ControlTargetData)
    positive: ControlSetData | None = None
    negative: ControlSetData | None = None
