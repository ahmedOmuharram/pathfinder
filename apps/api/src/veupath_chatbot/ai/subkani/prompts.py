"""Prompt builders for sub-kani execution."""

from __future__ import annotations


def build_subkani_round_prompt(
    *,
    task: str,
    goal: str,
    graph_id: str,
    dependency_context: str | None,
) -> str:
    dependency_block = (
        f"Dependency context:\n{dependency_context}\n\n" if dependency_context else ""
    )
    dependency_instruction = (
        "If dependency context lists step IDs, you MUST use those IDs "
        "instead of creating new steps.\n"
        if dependency_context
        else "If the dependency context is empty, call list_current_steps before proceeding.\n"
    )
    return (
        "You are a sub-agent helping to build a VEuPathDB strategy.\n"
        f"Overall goal: {goal}\n"
        f"Your task: {task}\n\n"
        f"{dependency_block}"
        f"{dependency_instruction}"
        "Use catalog tools to identify the best search and parameters.\n"
        "When the task mentions a species and stage, you MUST choose datasets \n"
        "and parameter values that match that species and stage. \n"
        "Do not substitute unrelated organisms or stages.\n"
        "For expression searches, ensure the sample/condition names include the "
        "requested stage (blood, liver, etc.) and the requested organism.\n"
        "If a study or journal name is mentioned, explicitly use the paper "
        "title or author name in the step display_name.\n"
        "Always pass a concise display_name when creating a step; "
        "the display_name must be human-readable and derived from the task, "
        "never a dataset URL or an internal search id.\n"
        "If asked to modify an existing node, update the existing step instead "
        "of creating a new one or rebuilding the graph.\n"
        f"Create the step in graph {graph_id} using create_search_step.\n"
        "Respond with a short confirmation after creating the step.\n"
    )

