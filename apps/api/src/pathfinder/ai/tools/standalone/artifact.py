"""Standalone artifact tools for pydantic-ai migration."""

from pydantic_ai import RunContext

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone._artifact_models import ConversationTitleResult
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error


async def set_conversation_title(
    ctx: RunContext[AgentDeps],
    title: str,
) -> ConversationTitleResult | ToolErrorPayload:
    """Update the conversation title displayed in the sidebar.

    Call early in the conversation once the user's intent is clear.
    Keep titles short and descriptive (e.g. 'Malaria gene expression analysis').

    Args:
        title: Short conversation title (will be trimmed of whitespace).
    """
    t = (title or "").strip()
    if not t:
        return tool_error("VALIDATION_ERROR", "title_required")
    return ConversationTitleResult(conversation_title=t)
