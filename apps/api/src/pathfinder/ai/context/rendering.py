"""Rendering helpers for cross-turn context compression and within-turn
graph state pinning.

``build_turn_summary`` / ``render_context_summary`` — cross-turn compression.
``render_graph_state`` / ``render_slim_step_result`` — within-turn graph state.
"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from pathfinder.ai.context.extractors import extract_tool_summary
from pathfinder.ai.context.models import ToolCallRecord, TurnSummary
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.plan import PlannedStep, StepType, StrategyPlan
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.types import SyncStateProtocol
from pathfinder.platform.types import JSONObject

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
_MAX_PLAN_PARAM_LEN = 60


# ---------------------------------------------------------------------------
# Plan node model (replaces isinstance/dict.get chains)
# ---------------------------------------------------------------------------


class _PlanNode(BaseModel):
    """Parse a recursive plan tree node from the projection JSON."""

    model_config = ConfigDict(extra="ignore")

    search_name: str = Field(default="?")
    display_name: str = Field(default="")
    parameters: JSONObject = Field(default_factory=dict)
    operator: str = Field(default="?")
    primary_input: "_PlanNode | None" = Field(default=None)
    secondary_input: "_PlanNode | None" = Field(default=None)


# ---------------------------------------------------------------------------
# Approved plan rendering
# ---------------------------------------------------------------------------


def _format_params_dict(params: Mapping[str, object]) -> str:
    """Format parameters as an inline dict string the model can copy."""
    if not params:
        return ""
    parts: list[str] = []
    for k, v in params.items():
        val = str(v)
        if len(val) > _MAX_PLAN_PARAM_LEN:
            val = val[: _MAX_PLAN_PARAM_LEN - 3] + "..."
        parts.append(f'"{k}": "{val}"')
    return "{" + ", ".join(parts) + "}"


def _render_plan_step_call(step: _PlanNode) -> str:
    """Render a single plan step as an executable tool call string."""
    if step.search_name == _COMBINE_SEARCH_NAME:
        primary_name = step.primary_input.display_name if step.primary_input else "?"
        secondary_name = (
            step.secondary_input.display_name if step.secondary_input else "?"
        )
        return (
            f'combine_steps("{primary_name}", "{secondary_name}", "{step.operator}")'
            f'  display_name="{step.display_name}"'
        )

    param_dict_str = _format_params_dict(step.parameters)

    if step.primary_input is not None and step.secondary_input is None:
        call = f'transform_step(input_step_id=<id of "{step.primary_input.display_name}">, transform_name="{step.search_name}"'
        if param_dict_str:
            call += f", parameters={param_dict_str}"
        return call + f', display_name="{step.display_name}")'

    call = f'create_leaf_step(search_name="{step.search_name}"'
    if param_dict_str:
        call += f", parameters={param_dict_str}"
    else:
        call += ", parameters={<FILL FROM get_search_overview>}"
    return call + f', display_name="{step.display_name}")'


def render_approved_plan(plan: JSONObject) -> str:
    """Render an approved strategy plan as pinned execution instructions.

    Takes the plan dict from StreamProjection.plan and produces a
    concise, actionable message telling the model exactly what steps
    to create and with what parameters.
    """
    raw_root = plan.get("root")
    if not raw_root:
        return ""

    root = _PlanNode.model_validate(raw_root)

    steps = _collect_plan_steps(root)
    if not steps:
        return ""

    lines = [
        "APPROVED PLAN — Execute these steps now. Do NOT re-discover or re-plan.",
        "Copy the EXACT parameters shown below into each tool call.",
        "",
    ]
    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. {_render_plan_step_call(step)}")

    return "\n".join(lines)


def _render_interactive_plan_step_call(
    step: PlannedStep,
    step_by_id: dict[str, PlannedStep],
    step_inputs: dict[str, dict[str, str]],
) -> str:
    """Render a planned step from the interactive plan model."""
    if step.step_type == StepType.COMBINE:
        inputs = step_inputs.get(step.id, {})
        primary = step_by_id.get(inputs.get("primary", ""))
        secondary = step_by_id.get(inputs.get("secondary", ""))
        primary_name = primary.display_name if primary else "?"
        secondary_name = secondary.display_name if secondary else "?"
        return (
            f'combine_steps("{primary_name}", "{secondary_name}", "{step.operator}")'
            f'  display_name="{step.display_name}"'
        )

    params = {
        parameter.name: parameter.value
        for parameter in step.parameters
        if parameter.value is not None
    }
    param_dict_str = _format_params_dict(params)

    if step.step_type == StepType.TRANSFORM:
        inputs = step_inputs.get(step.id, {})
        primary = step_by_id.get(inputs.get("primary", ""))
        primary_name = primary.display_name if primary else "?"
        call = (
            f'transform_step(input_step_id=<id of "{primary_name}">, '
            f'transform_name="{step.search_name}"'
        )
        if param_dict_str:
            call += f", parameters={param_dict_str}"
        return call + f', display_name="{step.display_name}")'

    call = f'create_leaf_step(search_name="{step.search_name}"'
    if param_dict_str:
        call += f", parameters={param_dict_str}"
    else:
        call += ", parameters={<FILL FROM get_search_overview>}"
    return call + f', display_name="{step.display_name}")'


def render_interactive_approved_plan(plan: StrategyPlan) -> str:
    """Render an approved interactive plan into execution instructions."""
    if not plan.steps:
        return ""

    try:
        steps = plan.steps_in_dependency_order()
    except ValueError:
        steps = list(plan.steps)

    step_by_id = {step.id: step for step in plan.steps}
    step_inputs: dict[str, dict[str, str]] = {}
    for connection in plan.connections:
        inputs = step_inputs.setdefault(connection.to_step, {})
        inputs[connection.input_type] = connection.from_step

    lines = [
        "APPROVED PLAN — Execute these steps now. Do NOT re-discover or re-plan.",
        "Copy the EXACT parameters shown below into each tool call.",
        "",
    ]
    for index, step in enumerate(steps, 1):
        lines.append(
            f"{index}. {_render_interactive_plan_step_call(step, step_by_id, step_inputs)}"
        )
    return "\n".join(lines)


def _collect_plan_steps(node: _PlanNode) -> list[_PlanNode]:
    """Flatten a recursive plan tree into execution order (leaves first)."""
    steps: list[_PlanNode] = []
    if node.primary_input is not None:
        steps.extend(_collect_plan_steps(node.primary_input))
    if node.secondary_input is not None:
        steps.extend(_collect_plan_steps(node.secondary_input))
    steps.append(node)
    return steps


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
