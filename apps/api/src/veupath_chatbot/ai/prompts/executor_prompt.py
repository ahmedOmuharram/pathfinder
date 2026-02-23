"""Prompt builders for the main agent."""

from __future__ import annotations

import json

from veupath_chatbot.ai.prompts.loader import load_system_prompt
from veupath_chatbot.platform.types import JSONObject


def build_agent_system_prompt(
    *,
    site_id: str,
    selected_nodes: JSONObject | None,
    mentioned_context: str | None = None,
) -> str:
    """Build the executor agent system prompt.

    :param site_id: VEuPathDB site identifier.
    :param selected_nodes: Selected graph nodes (default: None).
    :param mentioned_context: Rich context from @-mentioned entities (default: None).
    :returns: Full system prompt string.
    """
    base_prompt = load_system_prompt()
    site_context = (
        f"\n\n## Current Session\nYou are currently working with the **{site_id}** database. "
        "Use this site for all searches and operations unless the user asks to switch sites."
    )
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
            + mentioned_context
        )
    return base_prompt + site_context + node_context + mention_block
