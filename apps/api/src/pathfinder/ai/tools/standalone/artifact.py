"""Standalone artifact tools for pydantic-ai migration."""

from __future__ import annotations

from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._artifact_models import ConversationTitleResult
from pathfinder.ai.tools.standalone._stream_parts import conversation_title_chunk
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error


async def set_conversation_title(
    ctx: RunContext[AgentDeps],
    title: str,
) -> ToolReturn[ConversationTitleResult] | ToolErrorPayload:
    """Update the conversation title displayed in the sidebar.

    Call early in the conversation once the user's intent is clear.
    Keep titles short and descriptive (e.g. 'Malaria gene expression analysis').

    Args:
        title: Short conversation title (will be trimmed of whitespace).
    """
    t = (title or "").strip()
    if not t:
        return tool_error("VALIDATION_ERROR", "title_required")
    return ToolReturn(
        return_value=ConversationTitleResult(conversation_title=t),
        metadata=[conversation_title_chunk(t)],
    )
