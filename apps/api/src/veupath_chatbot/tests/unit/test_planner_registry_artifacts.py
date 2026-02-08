from __future__ import annotations

from typing import Any

import pytest

from veupath_chatbot.ai.tools.planner_registry import PlannerToolRegistryMixin
from veupath_chatbot.platform.types import JSONArray


class DummyPlanner(PlannerToolRegistryMixin):
    def __init__(self, artifacts: JSONArray) -> None:
        self.get_plan_session_artifacts = lambda: _async_return(artifacts)


async def _async_return(value: Any) -> Any:
    return value


@pytest.mark.asyncio
async def test_list_saved_planning_artifacts_compact() -> None:
    planner = DummyPlanner(
        [
            {"id": "a1", "title": "One", "createdAt": "t1", "summaryMarkdown": "x"},
            {"id": "a2", "title": "Two", "createdAt": "t2", "parameters": {"k": "v"}},
        ]
    )
    out = await planner.list_saved_planning_artifacts()
    assert out["ok"] is True
    assert out["artifacts"] == [
        {"id": "a1", "title": "One", "createdAt": "t1"},
        {"id": "a2", "title": "Two", "createdAt": "t2"},
    ]


@pytest.mark.asyncio
async def test_get_saved_planning_artifact_found() -> None:
    planner = DummyPlanner([{"id": "delegation_draft", "title": "Draft"}])
    out = await planner.get_saved_planning_artifact("delegation_draft")
    assert out["ok"] is True
    assert out["artifact"]["id"] == "delegation_draft"


@pytest.mark.asyncio
async def test_request_executor_build_loads_delegation_draft_when_plan_omitted() -> (
    None
):
    planner = DummyPlanner(
        [
            {
                "id": "delegation_draft",
                "title": "Delegation plan (draft)",
                "parameters": {"delegationPlan": {"type": "task", "task": "do thing"}},
            }
        ]
    )
    out = await planner.request_executor_build(
        delegation_goal="x",
        additional_instructions="y",
    )
    assert out["executorBuildRequest"]["delegationPlan"]["type"] == "task"
