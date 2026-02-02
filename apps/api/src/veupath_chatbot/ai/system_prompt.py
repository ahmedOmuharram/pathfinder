"""Prompt builders for the main agent."""

from __future__ import annotations

from veupath_chatbot.ai.prompts import load_system_prompt


def build_agent_system_prompt(*, site_id: str, selected_nodes: dict | None) -> str:
    base_prompt = load_system_prompt()
    site_context = (
        f"\n\n## Current Session\nYou are currently working with the **{site_id}** database. "
        "Use this site for all searches and operations unless the user asks to switch sites."
    )
    node_context = ""
    if selected_nodes:
        node_context = (
            "\n\n## Selected Nodes\n"
            "The user selected these graph nodes from the strategy view. "
            "Use their IDs when referencing or editing them:\n"
            f"{selected_nodes}"
        )
    return base_prompt + site_context + node_context

