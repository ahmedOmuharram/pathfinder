"""Prompt builders for sub-kani execution."""

from __future__ import annotations


def build_subkani_round_prompt(
    *,
    task: str,
    goal: str,
    graph_id: str,
    dependency_context: str | None,
) -> str:
    dependency_block = ""
    if dependency_context:
        dependency_block = (
            "## Dependency context (authoritative)\n"
            "Use the step ids from this context when the task depends on prior work.\n\n"
            "```json\n"
            f"{dependency_context}\n"
            "```\n\n"
        )

    return (
        "# Subtask execution (VEuPathDB strategy sub-agent)\n\n"
        f"## Overall goal\n{goal}\n\n"
        f"## Your task\n{task}\n\n"
        f"## Graph\nYou must operate on graphId: {graph_id}\n\n"
        f"{dependency_block}"
        "## Rules (must-follow)\n"
        "- Use tools; do not guess search names, parameter keys, or IDs.\n"
        "- If dependency context provides step ids, prefer using them over creating duplicates.\n"
        "- If dependency context is missing/empty and you need graph state, call `list_current_steps(graph_id=...)` first.\n"
        "- Always include `graph_id` in graph-editing tool calls.\n"
        "- Do not create a combine step unless the task explicitly instructs you AND provides the input step IDs.\n"
        "- If the task says modify/update/rename, update the existing step instead of creating a new step.\n\n"
        "## How to execute (repeatable)\n"
        "1. Identify whether this is **create** vs **edit**.\n"
        "2. If creating:\n"
        "   - Use `search_for_searches` (or `list_searches`) to find candidate searches.\n"
        "   - Use `get_search_parameters` to learn required params.\n"
        "   - Create exactly one correct step with `create_search_step`.\n"
        "   - If the search requires an input step, do not use `create_search_step`; use `transform_step` (or `find_orthologs` for orthology).\n"
        "3. If editing:\n"
        "   - Use `update_step_parameters` and/or `rename_step` for the specified step ids.\n\n"
        "## Biological/metadata constraints\n"
        "- If organism and/or life stage is specified, pick searches and parameter values matching both.\n"
        "- For expression tasks, ensure datasets/conditions correspond to the requested organism and stage.\n"
        "- If a study/paper is mentioned, reflect it in `display_name` when appropriate.\n\n"
        "## Parameter encoding (critical)\n"
        "- All parameter values must be strings.\n"
        "- Multi-pick vocab values must be JSON-string arrays like `\"[\\\"Plasmodium falciparum 3D7\\\"]\"`.\n"
        "- Range values must be JSON-string objects like `\"{\\\"min\\\": 1, \\\"max\\\": 5}\"`.\n\n"
        "## Response\n"
        "After you finish the tool calls, reply with 1–2 sentences confirming what you created/updated.\n"
    )

