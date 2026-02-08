from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.events import (
    CITATIONS,
    EXECUTOR_BUILD_REQUEST,
    PLANNING_ARTIFACT,
    tool_result_to_events,
)


def test_tool_result_to_events_emits_citations_and_planning_artifact() -> None:
    result: JSONObject = {
        "citations": [
            {"id": "c1", "source": "web", "title": "Example", "url": "https://x"}
        ],
        "planningArtifact": {"id": "p1", "title": "Plan", "summaryMarkdown": "x"},
    }
    events = tool_result_to_events(result)
    types = [e.get("type") for e in events]
    assert CITATIONS in types
    assert PLANNING_ARTIFACT in types


def test_tool_result_to_events_emits_executor_build_request() -> None:
    result: JSONObject = {
        "executorBuildRequest": {
            "siteId": "plasmodb",
            "message": "Build it",
            "delegationGoal": "x",
            "delegationPlan": {"id": "root", "kind": "task", "task": "do thing"},
        }
    }
    events = tool_result_to_events(result)
    assert any(e.get("type") == EXECUTOR_BUILD_REQUEST for e in events)
