"""System prompt builder for workbench chat conversations."""

import json
from functools import lru_cache

from pathfinder.ai.prompts.loader import load_system_prompt
from pathfinder.platform.langfuse.prompts import load_prompt
from pathfinder.platform.types import JSONObject


@lru_cache(maxsize=1)
def _load_workbench_prompt() -> str:
    return load_prompt("workbench")


def build_workbench_system_prompt(
    *,
    site_id: str,
    experiment_context: JSONObject,
) -> str:
    """Build the system prompt for a workbench chat conversation.

    Composes shared base prompt (system.md + safety.md + site_hints.md)
    with workbench-specific instructions and experiment context.
    """
    base = load_system_prompt()
    workbench = _load_workbench_prompt()
    site_block = (
        f"\n\n## Current Session\nSite: **{site_id}**. "
        "Use this site for all searches and operations."
    )
    context_block = ""
    if experiment_context:
        context_block = (
            "\n\n## Experiment Context\n"
            "```json\n" + json.dumps(experiment_context, indent=2) + "\n```"
        )
    return base + "\n\n---\n\n" + workbench + site_block + context_block
