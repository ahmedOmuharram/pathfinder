"""Prompt loading helpers for the AI agent."""

from __future__ import annotations

from pathlib import Path

# All .md prompt files live alongside this module.
_PROMPTS_DIR = Path(__file__).parent


def load_system_prompt() -> str:
    """Load and combine the unified system prompt."""
    parts: list[str] = []
    for filename in ("system.md", "safety.md", "site_hints.md"):
        prompt_file = _PROMPTS_DIR / filename
        if prompt_file.exists():
            parts.append(prompt_file.read_text())
    return "\n\n---\n\n".join(parts)
