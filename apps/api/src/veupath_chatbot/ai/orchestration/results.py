"""Typed execution results for delegation nodes.

Every node execution (task or combine) produces one of these result types.
They carry the structured output from sub-kani runs and combine operations,
replacing the untyped JSONObject dicts that previously flowed through the
scheduler and response builder.
"""

from typing import Literal

from pydantic import Field, computed_field

from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONArray


class TaskResult(CamelModel):
    """Result of executing a task node via sub-kani."""

    id: str
    task: str
    kind: Literal["task"] = "task"
    instructions: str = ""
    steps: JSONArray = Field(default_factory=list)
    notes: str | None = None
    subtree_root: str | None = None
    errors: list[str] | None = None
    error: str | None = None
    ok: bool | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def output_step_id(self) -> str | None:
        return self.subtree_root


class CombineResult(CamelModel):
    """Result of executing a combine node."""

    id: str
    task: str
    kind: Literal["combine"] = "combine"
    operator: str | None = None
    inputs: list[str] | None = None
    steps: JSONArray = Field(default_factory=list)
    step_id: str | None = None
    graph_id: str | None = None
    error: str | None = None
    ok: bool | None = None
    missing: list[str] | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def output_step_id(self) -> str | None:
        return self.step_id


NodeResult = TaskResult | CombineResult
