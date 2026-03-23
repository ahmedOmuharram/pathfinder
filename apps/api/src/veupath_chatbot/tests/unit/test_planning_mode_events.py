from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.events import (
    EventType,
    tool_result_to_events,
)


def test_tool_result_to_events_emits_citations_and_planning_artifact() -> None:
    result: JSONObject = {
        "citations": [
            {"id": "c1", "source": "web", "title": "Example", "url": "https://x"}
        ],
        "planningArtifact": {
            "id": "p1",
            "title": "New Conversation",
            "summaryMarkdown": "x",
        },
    }
    events = tool_result_to_events(result)
    types = [e.get("type") for e in events]
    assert EventType.CITATIONS in types
    assert EventType.PLANNING_ARTIFACT in types


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
    assert any(e.get("type") == EventType.EXECUTOR_BUILD_REQUEST for e in events)
