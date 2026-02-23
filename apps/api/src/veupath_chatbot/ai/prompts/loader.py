"""Prompt loading helpers for the AI agent."""

from __future__ import annotations

from pathlib import Path


def load_system_prompt() -> str:
    """Load and combine system prompts."""
    prompts_dir = Path(__file__).parent / "prompts"

    parts: list[str] = []
    for filename in ["system.md", "safety.md", "site_hints.md"]:
        prompt_file = prompts_dir / filename
        if prompt_file.exists():
            parts.append(prompt_file.read_text())

    return "\n\n---\n\n".join(parts)


def load_planner_prompt() -> str:
    """Load and combine system prompts for planning mode."""
    prompts_dir = Path(__file__).parent / "prompts"

    parts: list[str] = []
    for filename in ["planner.md", "safety.md", "site_hints.md"]:
        prompt_file = prompts_dir / filename
        if prompt_file.exists():
            parts.append(prompt_file.read_text())

    return "\n\n---\n\n".join(parts)
