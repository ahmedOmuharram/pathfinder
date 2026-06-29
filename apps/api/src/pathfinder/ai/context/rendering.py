"""Rendering helpers for cross-turn context compression and within-turn
graph state pinning.

``build_turn_summary`` / ``render_context_summary`` — cross-turn compression.
``render_graph_state`` / ``render_slim_step_result`` — within-turn graph state.
"""

from pathfinder.ai.context.extractors import extract_tool_summary
from pathfinder.ai.context.models import ToolCallRecord, TurnSummary
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.types import SyncStateProtocol

_MAX_KEY_ARGS = 2
_MAX_ARG_LEN = 30
_MAX_TURN_SUMMARIES = 15


# ---------------------------------------------------------------------------
# Key-arg formatting
# ---------------------------------------------------------------------------


def _format_key_args(record: ToolCallRecord) -> str:
    """Extract the first few string-valued arguments and format them."""
    parts: list[str] = []
    for key, val in record.arguments.items():
        if not isinstance(val, str):
            continue
        display = val if len(val) <= _MAX_ARG_LEN else val[:_MAX_ARG_LEN] + "..."
        parts.append(f"{key}='{display}'")
        if len(parts) >= _MAX_KEY_ARGS:
            break
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_turn_summary(
    turn_number: int,
    records: list[ToolCallRecord],
) -> TurnSummary:
    """Build a TurnSummary from tool call records.

    For each record, format as ``tool_name(key_args) -> extracted_summary``
    where key_args are the first 2 string-valued arguments (truncated to 30
    chars each).
    """
    tool_summaries: list[str] = []
    for record in records:
        key_args = _format_key_args(record)
        extracted = extract_tool_summary(record)
        if key_args:
            formatted = f"{record.name}({key_args}) \u2192 {extracted}"
        else:
            formatted = f"{record.name} \u2192 {extracted}"
        tool_summaries.append(formatted)
    return TurnSummary(
        turn_number=turn_number,
        tool_summaries=tool_summaries,
    )


def render_context_summary(summaries: list[TurnSummary]) -> str:
    """Render TurnSummary objects into the pinned context string.

    Format::

        Previous tool activity (summarized):

        Turn 1: get_search_overview(searchName='GenesByGoTerm') -> 7 params. ...
        Turn 2: create_leaf_step -> step_1, 234 genes.

    Returns empty string if no summaries have tool activity.
    Skips turns with empty tool_summaries.
    Keeps only the most recent ``_MAX_TURN_SUMMARIES`` turns to prevent
    unbounded growth in long conversations.
    """
    # Cap: keep only the most recent turns.
    capped = (
        summaries[-_MAX_TURN_SUMMARIES:]
        if len(summaries) > _MAX_TURN_SUMMARIES
        else summaries
    )
    lines: list[str] = []
    for summary in capped:
        if not summary.tool_summaries:
            continue
        calls_str = " ".join(summary.tool_summaries)
        lines.append(f"Turn {summary.turn_number}: {calls_str}")
    if not lines:
        return ""
    header = "Previous tool activity (summarized):\n"
    return header + "\n".join(lines)


# ---------------------------------------------------------------------------
# Within-turn graph state rendering
# ---------------------------------------------------------------------------

_COMBINE_SEARCH_NAME = "__combine__"
_MAX_PARAM_VAL_LEN = 40


def _render_step_header(step_id: str, step: StrategyStepNode) -> list[str]:
    """Render the header parts for a single step."""
    kind = step.infer_kind()
    parts: list[str] = [f"{step_id}:"]

    if kind == "combine":
        op = step.operator or "?"
        primary = step.primary_input.id if step.primary_input else "?"
        secondary = step.secondary_input.id if step.secondary_input else "?"
        parts.append(f"{op}({primary}, {secondary})")
    elif kind == "transform":
        parts.append(f"{step.search_name} [transform]")
        input_id = step.primary_input.id if step.primary_input else "?"
        parts.append(f"input={input_id}")
    else:
        parts.append(f"{step.search_name} [leaf]")

    if step.display_name:
        parts.append(f'"{step.display_name}"')
    return parts


def _render_step_suffix(
    step_id: str,
    sync_state: SyncStateProtocol | None,
    *,
    is_root: bool,
) -> str:
    """Render the suffix (counts, wdk ID, errors) for a step."""
    count = sync_state.step_counts.get(step_id) if sync_state else None
    wdk_id = sync_state.wdk_step_ids.get(step_id) if sync_state else None
    push_error = sync_state.wdk_push_errors.get(step_id) if sync_state else None

    validation = sync_state.step_validations.get(step_id) if sync_state else None

    suffix_parts: list[str] = []
    if count is not None:
        suffix_parts.append(f"{count:,} genes")
    if wdk_id is not None:
        suffix_parts.append(f"wdk={wdk_id}")
    if is_root:
        suffix_parts.append("root")
    if push_error:
        suffix_parts.append(f"ERROR: {push_error[:60]}")
    if validation and not validation.is_valid:
        general = validation.errors.general if validation.errors else []
        if general:
            suffix_parts.append(f"INVALID: {str(general[0])[:60]}")
        else:
            suffix_parts.append("INVALID")
    if suffix_parts:
        return f"\u2192 {', '.join(suffix_parts)}"
    return ""


def _render_step_params(step: StrategyStepNode) -> str:
    """Render parameters as a compact indented line."""
    if not step.parameters:
        return ""
    param_strs: list[str] = []
    for k, v in step.parameters.items():
        val_str = str(v)
        if len(val_str) > _MAX_PARAM_VAL_LEN:
            val_str = val_str[: _MAX_PARAM_VAL_LEN - 3] + "..."
        param_strs.append(f"{k}={val_str}")
    return "\n  " + ", ".join(param_strs)


def render_graph_state(
    graph: StrategyGraph,
    sync_state: SyncStateProtocol | None = None,
) -> str:
    """Render the current strategy graph as a compact text summary.

    Pinned in ``always_included_messages`` so the model always sees the
    current graph state without needing the full JSON snapshot in every
    tool result.
    """
    if not graph.steps:
        return ""

    lines: list[str] = []
    for step_id, step in graph.steps.items():
        parts = _render_step_header(step_id, step)
        suffix = _render_step_suffix(
            step_id, sync_state, is_root=step_id in graph.roots
        )
        if suffix:
            parts.append(suffix)
        line = " ".join(parts)
        if step.infer_kind() != "combine":
            line += _render_step_params(step)
        lines.append(line)

    header = f"Current strategy graph ({len(graph.steps)} steps):"
    wdk_strategy_id = sync_state.wdk_strategy_id if sync_state else None
    if wdk_strategy_id:
        header += f" wdk_strategy={wdk_strategy_id}"
    return header + "\n\n" + "\n\n".join(lines)


def render_slim_step_result(
    step_id: str,
    search_name: str,
    display_name: str | None,
    estimated_size: int | None,
    *,
    operator: str | None = None,
    input_ids: tuple[str, str] | None = None,
) -> str:
    """Render a slim one-line tool result for a graph-mutating tool call.

    Replaces the full ``StepOkResponse`` JSON in the model's chat history.
    """
    parts: list[str] = ["ok:", step_id]

    if operator and input_ids:
        parts.append(f"{operator}({input_ids[0]}, {input_ids[1]})")
    elif search_name and search_name != _COMBINE_SEARCH_NAME:
        parts.append(search_name)

    if display_name:
        parts.append(f'"{display_name}"')

    if estimated_size is not None:
        parts.append(f"{estimated_size:,} genes")

    return " ".join(parts)
