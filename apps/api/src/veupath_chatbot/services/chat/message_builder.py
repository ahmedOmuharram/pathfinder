"""Assistant message assembly and content accumulation."""

from __future__ import annotations

from datetime import UTC, datetime

from veupath_chatbot.persistence.repo import StrategyRepository
from veupath_chatbot.platform.types import JSONArray, JSONObject

from .thinking import normalize_subkani_activity, normalize_tool_calls


async def build_and_persist_messages(
    *,
    strategy_repo: StrategyRepository,
    strategy_id: object,
    assistant_messages: list[str],
    citations: JSONArray,
    planning_artifacts: JSONArray,
    reasoning: str | None,
    optimization_progress: JSONObject | None,
    tool_calls: JSONArray,
    subkani_calls: dict[str, JSONArray],
    subkani_status: dict[str, str],
) -> None:
    normalized_tool_calls = normalize_tool_calls(tool_calls)
    normalized_subkani = normalize_subkani_activity(subkani_calls, subkani_status)

    if not assistant_messages and (normalized_tool_calls or normalized_subkani):
        assistant_messages.append("Done.")

    for index, content in enumerate(assistant_messages):
        tool_calls_payload = (
            normalized_tool_calls
            if normalized_tool_calls and index == len(assistant_messages) - 1
            else None
        )
        subkani_payload = (
            normalized_subkani
            if normalized_subkani and index == len(assistant_messages) - 1
            else None
        )
        assistant_message: JSONObject = {
            "role": "assistant",
            "content": content,
            "toolCalls": tool_calls_payload,
            "subKaniActivity": subkani_payload,
            "mode": "execute",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if index == len(assistant_messages) - 1:
            if citations:
                assistant_message["citations"] = citations
            if planning_artifacts:
                assistant_message["planningArtifacts"] = planning_artifacts
            if reasoning:
                assistant_message["reasoning"] = reasoning
            if optimization_progress:
                assistant_message["optimizationProgress"] = optimization_progress
        await strategy_repo.add_message(strategy_id, assistant_message)
