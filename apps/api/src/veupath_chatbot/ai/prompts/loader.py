"""Prompt loading helpers for the AI agent."""

from pathlib import Path

# All .md prompt files live alongside this module.
_PROMPTS_DIR = Path(__file__).parent


def load_system_prompt(*, include_site_hints: bool = True) -> str:
    """Load and combine the unified system prompt.

    :param include_site_hints: When False, skip site_hints.md to save ~400
        tokens on continuation turns where the model already has site context.
    """
    filenames = ["system.md", "safety.md"]
    if include_site_hints:
        filenames.append("site_hints.md")
    parts: list[str] = []
    for filename in filenames:
        prompt_file = _PROMPTS_DIR / filename
        if prompt_file.exists():
            parts.append(prompt_file.read_text())
    return "\n\n---\n\n".join(parts)
