"""Prompt builders for the main agent."""

import json

from pathfinder.ai.prompts.loader import load_system_prompt
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.types import JSONObject


def _build_strategy_context(session: StrategySession) -> str:
    """Build a brief strategy summary for injection into the system prompt.

    Gives the model persistent awareness of the current strategy state so it
    does not lose track of already-built steps across turns.
    """
    graph = session.get_graph(None)
    if not graph or not graph.steps:
        return ""

    lines: list[str] = ["\n\n## Current Strategy State"]
    lines.append(f"**Name:** {graph.name}")
    if graph.record_type:
        lines.append(f"**Record type:** {graph.record_type}")

    built = graph.wdk_strategy_id is not None
    lines.append(f"**Built on WDK:** {'Yes (ID: ' + str(graph.wdk_strategy_id) + ')' if built else 'No'}")
    lines.append(f"**Steps ({len(graph.steps)}):**")

    for step in graph.steps.values():
        kind = step.infer_kind()
        label = step.display_name or step.search_name
        count = graph.step_counts.get(step.id)
        count_str = f" — {count:,} results" if count is not None else ""
        error = graph.wdk_push_errors.get(step.id)
        error_str = f" ⚠ {error}" if error else ""

        if kind == "combine":
            lines.append(
                f"- `{step.id}` [{kind}] {step.operator}: {label}{count_str}{error_str}"
            )
        elif kind == "transform":
            lines.append(f"- `{step.id}` [{kind}] {label}{count_str}{error_str}")
        else:
            lines.append(f"- `{step.id}` [search] {label}{count_str}{error_str}")

    lines.append(
        "\nDo NOT re-create steps that already exist. "
        "Use `get_strategy` for full parameter details if needed."
    )
    return "\n".join(lines)


def build_agent_system_prompt(
    *,
    site_id: str,
    strategy_session: StrategySession,
    selected_nodes: JSONObject | None,
    mentioned_context: str | None = None,
    is_continuation: bool = False,
) -> str:
    """Build the executor agent system prompt.

    :param site_id: VEuPathDB site identifier.
    :param strategy_session: Current strategy session with graph state.
    :param selected_nodes: Selected graph nodes (default: None).
    :param mentioned_context: Rich context from @-mentioned entities (default: None).
    :param is_continuation: True when this is not the first turn (chat_history
        or context_summary present). Skips site_hints.md to save tokens and
        omits strategy step details (pinned graph state is more current).
    :returns: Full system prompt string.
    """
    base_prompt = load_system_prompt(include_site_hints=not is_continuation)
    site_context = (
        f"\n\n## Current Session\nYou are currently working with the **{site_id}** database. "
        "Use this site for all searches and operations unless the user asks to switch sites."
    )
    # When the strategy has steps, the pinned graph state in
    # always_included_messages is always more current — skip the
    # duplicate step listing from the system prompt.
    graph = strategy_session.get_graph(None)
    has_steps = graph is not None and bool(graph.steps)
    strategy_context = "" if has_steps else _build_strategy_context(strategy_session)
    node_context = ""
    if selected_nodes:
        selected_nodes_json = json.dumps(selected_nodes, indent=2, sort_keys=True)
        node_context = (
            "\n\n## Selected Nodes\n"
            "The user selected these graph nodes from the strategy view. "
            "Use their IDs when referencing or editing them:\n"
            f"```json\n{selected_nodes_json}\n```"
        )
    mention_block = ""
    if mentioned_context:
        mention_block = (
            "\n\n## Referenced Context\n"
            "The user @-mentioned the following entities. Use this information "
            "to understand their question and provide relevant answers.\n\n"
            "```\n" + mentioned_context + "\n```"
        )
    return base_prompt + site_context + strategy_context + node_context + mention_block
