"""History reconstruction from Redis stream messages.

Extracts a compressed context summary and discovered searches from persisted
message history.  The orchestration pipeline does not pass reconstructed
ChatMessage objects to agents — each phase starts with fresh history.
"""

import json
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.context.models import ToolCallRecord, TurnSummary
from pathfinder.ai.context.rendering import (
    build_turn_summary,
    render_context_summary,
)
from pathfinder.ai.orchestration.phase_results import PhaseName, ProblemFrame
from pathfinder.platform.event_schemas_pipeline import PhaseChangeEventData
from pathfinder.platform.logging import get_logger
from pathfinder.platform.parsing import parse_jsonish
from pathfinder.platform.types import JSONObject, JSONValue
from pathfinder.services.catalog.overview_formatting import SearchOverviewResult

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models for parsing Redis message dicts (replace isinstance chains)
# ---------------------------------------------------------------------------


class _RawToolCall(BaseModel):
    """Parse a single tool call from the Redis stream JSON (camelCase)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = ""
    name: str = ""
    arguments: dict[str, JSONValue] = Field(default_factory=dict)
    result: str = ""
    is_error: bool = Field(default=False, alias="isError")


class _RawAssistantMessage(BaseModel):
    """Parse an assistant message from the Redis stream."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    role: str = ""
    content: str = ""
    tool_calls: list[_RawToolCall] = Field(
        default_factory=list, alias="toolCalls"
    )


@dataclass
class ReconstructedHistory:
    """Result of reconstructing chat history from Redis messages."""

    context_summary: str | None = None
    discovered_searches: dict[str, SearchOverview] = field(default_factory=dict)
    problem_frame: ProblemFrame | None = None
    resume_phase: PhaseName | None = None


# ---------------------------------------------------------------------------
# Turn grouping
# ---------------------------------------------------------------------------

type _Turn = list[JSONObject]
type _RedisStreamEntry = tuple[str, dict[str, str]]


def _group_into_turns(messages: list[JSONObject]) -> list[_Turn]:
    """Group messages into turns. Each user message starts a new turn."""
    turns: list[_Turn] = []
    current: _Turn = []
    for msg in messages:
        parsed = _RawAssistantMessage.model_validate(msg)
        if parsed.role == "user":
            if current:
                turns.append(current)
            current = [msg]
        else:
            current.append(msg)
    if current:
        turns.append(current)
    return turns


# ---------------------------------------------------------------------------
# Tool call record extraction
# ---------------------------------------------------------------------------


def _raw_to_record(raw: _RawToolCall) -> ToolCallRecord:
    """Convert a parsed raw tool call to a ToolCallRecord."""
    return ToolCallRecord(
        id=raw.id,
        name=raw.name,
        arguments=raw.arguments,
        result=raw.result,
        is_error=raw.is_error,
    )


def _extract_all_records(msg: JSONObject) -> list[ToolCallRecord]:
    """Extract all tool call records from an assistant message."""
    parsed = _RawAssistantMessage.model_validate(msg)
    if parsed.role != "assistant":
        return []

    return [_raw_to_record(tc) for tc in parsed.tool_calls]


# ---------------------------------------------------------------------------
# Turn summarisation (older turns → TurnSummary)
# ---------------------------------------------------------------------------


def _summarise_turn(
    turn: _Turn,
    turn_number: int,
) -> TurnSummary | None:
    """Build a TurnSummary from tool activity in an older turn."""
    all_records: list[ToolCallRecord] = []

    for msg in turn:
        all_records.extend(_extract_all_records(msg))

    if not all_records:
        return None
    return build_turn_summary(turn_number, all_records)


# ---------------------------------------------------------------------------
# Discovery extraction
# ---------------------------------------------------------------------------


def _extract_discovered_searches(
    turns: list[_Turn],
) -> dict[str, SearchOverview]:
    """Extract search overviews from get_search_overview calls across all turns.

    Parses the tool result JSON to recover parameter names and required params,
    so that the discovery gate on subsequent turns carries the full schema —
    not just a name stub.  Falls back to a minimal stub when parsing fails.
    """
    discovered: dict[str, SearchOverview] = {}
    for turn in turns:
        for msg in turn:
            records = _extract_all_records(msg)
            for record in records:
                if record.name != "get_search_overview" or record.is_error:
                    continue
                search_name = record.arguments.get("search_name")
                if not search_name:
                    continue
                name_str = str(search_name)
                try:
                    overview_result = SearchOverviewResult.model_validate_json(
                        record.result
                    )
                    all_param_names = [
                        p.name for p in overview_result.required
                    ] + [p.name for p in overview_result.optional]
                    required_names = [p.name for p in overview_result.required]
                    discovered[name_str] = SearchOverview(
                        search_name=overview_result.search_name,
                        display_name=overview_result.display_name,
                        record_type=overview_result.record_type,
                        description=overview_result.description,
                        parameter_names=all_param_names,
                        required_params=required_names,
                    )
                except (ValidationError, ValueError, KeyError):
                    logger.warning(
                        "Failed to parse get_search_overview result for %s, "
                        "falling back to stub. result=%s",
                        name_str,
                        record.result[:200] if record.result else "(empty)",
                        exc_info=True,
                    )
                    if name_str not in discovered:
                        discovered[name_str] = SearchOverview(
                            search_name=name_str,
                            display_name=name_str,
                            record_type="transcript",
                            description="",
                            parameter_names=[],
                            required_params=[],
                        )
    return discovered


def _extract_latest_problem_frame(turns: list[_Turn]) -> ProblemFrame | None:
    """Extract the latest problem frame saved by set_problem_frame."""
    latest: ProblemFrame | None = None
    for turn in turns:
        for msg in turn:
            for record in _extract_all_records(msg):
                if record.name != "set_problem_frame" or record.is_error:
                    continue
                parsed = parse_jsonish(record.result)
                if not isinstance(parsed, dict):
                    continue
                raw_frame = parsed.get("problemFrame")
                if not isinstance(raw_frame, dict):
                    continue
                try:
                    latest = ProblemFrame.model_validate(raw_frame)
                except ValidationError:
                    logger.warning(
                        "Failed to parse set_problem_frame result",
                        exc_info=True,
                    )
    return latest


def extract_resume_phase_from_entries(
    entries: list[_RedisStreamEntry],
) -> PhaseName | None:
    """Return the last paused phase if the conversation is awaiting input."""
    latest_phase_change: PhaseChangeEventData | None = None
    for _entry_id, fields in entries:
        if fields.get("type", "") != "phase_change":
            continue
        try:
            payload = json.loads(fields["data"])
            latest_phase_change = PhaseChangeEventData.model_validate(payload)
        except (json.JSONDecodeError, KeyError, ValidationError):
            continue

    if latest_phase_change is None:
        return None
    if latest_phase_change.status != "awaiting_input":
        return None
    if latest_phase_change.phase not in (
        "scoping",
        "discovery",
        "planning",
        "verification",
    ):
        return None
    return latest_phase_change.phase


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def reconstruct_history(
    messages: list[JSONObject],
    *,
    recent_turn_count: int = 3,
    resume_phase: PhaseName | None = None,
) -> ReconstructedHistory:
    """Reconstruct context summary and discovered searches from Redis messages.

    Groups messages into turns, builds compressed TurnSummary objects for older
    turns (beyond the most recent ``recent_turn_count``), and extracts
    discovered searches from get_search_overview tool calls across all turns.
    """
    if not messages:
        return ReconstructedHistory()

    turns = _group_into_turns(messages)
    split_idx = max(0, len(turns) - recent_turn_count)
    older_turns = turns[:split_idx]

    turn_summaries: list[TurnSummary] = []

    for i, turn in enumerate(older_turns, start=1):
        summary = _summarise_turn(turn, turn_number=i)
        if summary is not None:
            turn_summaries.append(summary)

    context_summary: str | None = None
    rendered = render_context_summary(turn_summaries)
    if rendered:
        context_summary = rendered

    discovered = _extract_discovered_searches(turns)
    problem_frame = _extract_latest_problem_frame(turns)

    return ReconstructedHistory(
        context_summary=context_summary,
        discovered_searches=discovered,
        problem_frame=problem_frame,
        resume_phase=resume_phase,
    )
