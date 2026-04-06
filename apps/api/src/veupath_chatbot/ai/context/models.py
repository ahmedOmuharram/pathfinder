"""Core models for cross-turn context management."""

from pydantic import BaseModel

from veupath_chatbot.platform.types import JSONValue


class ToolCallRecord(BaseModel):
    """A single tool call as reconstructed from Redis events."""

    id: str
    name: str
    arguments: dict[str, JSONValue]
    result: str
    is_error: bool = False


class TurnSummary(BaseModel):
    """Compressed representation of one turn's tool activity."""

    turn_number: int
    tool_summaries: list[str]
