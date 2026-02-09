"""Planning-mode stream processor + persistence (plan sessions)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from veupath_chatbot.persistence.models import PlanSession
from veupath_chatbot.persistence.repo import PlanSessionRepository
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.chat.sse import sse_error, sse_event, sse_message_start
from veupath_chatbot.services.chat.thinking import (
    build_thinking_payload,
    normalize_tool_calls,
)

logger = get_logger(__name__)


class PlanStreamProcessor:
    """Stateful processor for a single streamed planning-mode chat turn."""

    def __init__(
        self,
        *,
        plan_repo: PlanSessionRepository,
        user_id: UUID,
        plan_session: PlanSession,
        plan_payload: JSONObject,
        mode: str = "plan",
    ) -> None:
        self.plan_repo = plan_repo
        self.user_id = user_id
        self.plan_session = plan_session
        self.plan_payload = plan_payload
        self.mode = mode

        self.assistant_messages: list[str] = []
        self.tool_calls: JSONArray = []
        self.tool_calls_by_id: dict[str, JSONObject] = {}
        self.citations: JSONArray = []
        self.planning_artifacts: JSONArray = []
        self.reasoning: str | None = None

        self.thinking_dirty = False

    def start_event(self) -> str:
        return sse_message_start(
            plan_session_id=str(self.plan_session.id),
            plan_session=self.plan_payload,
        )

    async def _flush_thinking(self) -> None:
        if not self.thinking_dirty:
            return
        payload = build_thinking_payload(
            self.tool_calls_by_id, {}, {}, reasoning=self.reasoning
        )
        await self.plan_repo.update_thinking(self.plan_session.id, payload)
        self.thinking_dirty = False

    async def on_event(self, event_type: str, event_data: JSONObject) -> str | None:
        if event_type == "message_start":
            return None

        if event_type == "assistant_message":
            content_value = event_data.get("content", "")
            content_str = str(content_value) if content_value is not None else ""
            content = content_str.strip()
            if content:
                self.assistant_messages.append(content)

        elif event_type == "tool_call_start":
            call_id_value = event_data.get("id")
            call_id = str(call_id_value) if isinstance(call_id_value, str) else None
            if call_id:
                self.tool_calls_by_id[call_id] = {
                    "id": call_id,
                    "name": event_data.get("name"),
                    "arguments": event_data.get("arguments"),
                }
                self.thinking_dirty = True
                await self._flush_thinking()

        elif event_type == "tool_call_end":
            call_id_value = event_data.get("id")
            call_id = str(call_id_value) if isinstance(call_id_value, str) else None
            if call_id and call_id in self.tool_calls_by_id:
                self.tool_calls_by_id[call_id]["result"] = event_data.get("result")
                self.tool_calls.append(self.tool_calls_by_id[call_id])
                self.thinking_dirty = True
                await self._flush_thinking()

        elif event_type == "citations":
            citations = event_data.get("citations")
            if isinstance(citations, list):
                self.citations.extend([c for c in citations if isinstance(c, dict)])

        elif event_type == "planning_artifact":
            artifact = event_data.get("planningArtifact")
            if isinstance(artifact, dict):
                self.planning_artifacts.append(artifact)

        elif event_type == "reasoning":
            text = event_data.get("reasoning")
            if isinstance(text, str) and text.strip():
                self.reasoning = text
                self.thinking_dirty = True
                await self._flush_thinking()

        elif event_type == "plan_update":
            title = event_data.get("title")
            if isinstance(title, str) and title.strip():
                await self.plan_repo.update_title(
                    plan_session_id=self.plan_session.id,
                    user_id=self.user_id,
                    title=title.strip(),
                )

        return sse_event(event_type, event_data)

    async def finalize(self) -> list[str]:
        normalized_tool_calls = normalize_tool_calls(self.tool_calls)
        # Persist final thinking so reasoning survives refresh without implying streaming.
        # Completed calls go under `lastToolCalls`; `toolCalls` is emptied.
        if normalized_tool_calls or (
            isinstance(self.reasoning, str) and self.reasoning.strip()
        ):
            final_thinking = build_thinking_payload(
                {}, {}, {}, reasoning=self.reasoning
            )
            final_thinking["toolCalls"] = []
            final_thinking["lastToolCalls"] = normalized_tool_calls
            await self.plan_repo.update_thinking(self.plan_session.id, final_thinking)
        else:
            await self.plan_repo.clear_thinking(self.plan_session.id)
        if not self.assistant_messages and normalized_tool_calls:
            self.assistant_messages = ["Done."]

        for index, content in enumerate(self.assistant_messages):
            msg: JSONObject = {
                "role": "assistant",
                "content": content,
                "toolCalls": normalized_tool_calls
                if index == len(self.assistant_messages) - 1
                else None,
                "mode": self.mode,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            if index == len(self.assistant_messages) - 1:
                if self.citations:
                    msg["citations"] = self.citations
                if self.planning_artifacts:
                    msg["planningArtifacts"] = self.planning_artifacts
            await self.plan_repo.add_message(self.plan_session.id, msg)

        if self.planning_artifacts:
            await self.plan_repo.append_planning_artifacts(
                self.plan_session.id, self.planning_artifacts
            )

        return []

    async def handle_exception(self, e: Exception) -> str:
        logger.error("Plan chat error", error=str(e))
        await self.plan_repo.clear_thinking(self.plan_session.id)
        return sse_error(str(e))
