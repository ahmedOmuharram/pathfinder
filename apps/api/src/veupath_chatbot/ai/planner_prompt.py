"""Prompt builders for the planning-mode agent."""

from __future__ import annotations

import json

from veupath_chatbot.ai.prompts import load_planner_prompt


def build_planner_system_prompt(
    *,
    site_id: str,
    selected_nodes: dict | None,
    delegation_draft_artifact: dict | None = None,
) -> str:
    base_prompt = load_planner_prompt()
    site_context = (
        f"\n\n## Current Session\nYou are currently working with the **{site_id}** database. "
        "Use this site for all searches and operations unless the user asks to switch sites."
    )
    draft_context = ""
    if delegation_draft_artifact:
        goal = (
            (delegation_draft_artifact.get("parameters") or {}).get("delegationGoal")
            if isinstance(delegation_draft_artifact.get("parameters"), dict)
            else None
        )
        plan = (
            (delegation_draft_artifact.get("parameters") or {}).get("delegationPlan")
            if isinstance(delegation_draft_artifact.get("parameters"), dict)
            else None
        )
        # Only inject when we have something non-empty; avoid "phantom drafts".
        if (goal and str(goal).strip()) or plan:
            plan_json = json.dumps(plan, indent=2, sort_keys=True) if plan else "null"
            draft_context = (
                "\n\n## Delegation Plan Draft (saved)\n"
                "A delegation plan draft already exists for this plan session. Treat it as the **current source of truth**.\n"
                "- Do **not** restart from scratch unless the user asks.\n"
                "- Before running catalog/search tools, review this draft and only fetch missing metadata needed to update it.\n"
                "\n"
                f"**Delegation goal**: {str(goal).strip() if goal else ''}\n"
                "\n"
                "```json\n"
                f"{plan_json}\n"
                "```"
            )
    node_context = ""
    if selected_nodes:
        selected_nodes_json = json.dumps(selected_nodes, indent=2, sort_keys=True)
        node_context = (
            "\n\n## Selected Nodes\n"
            "The user selected these graph nodes from the strategy view. "
            "Use their IDs when referencing existing steps; do not modify the graph unless asked.\n"
            f"```json\n{selected_nodes_json}\n```"
        )
    return base_prompt + site_context + draft_context + node_context

