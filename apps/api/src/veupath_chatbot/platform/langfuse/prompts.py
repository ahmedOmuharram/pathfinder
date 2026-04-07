"""Langfuse-backed prompt management with local file fallback.

Prompt lifecycle:
1. Try Langfuse SDK (versioned, A/B testable, rollbackable from dashboard)
2. Fall back to local .md files (always works, even without Langfuse)
3. On first Langfuse startup, seed prompts from local files if missing
"""

from pathlib import Path

import langfuse.api

from veupath_chatbot.platform.langfuse.client import get_langfuse
from veupath_chatbot.platform.logging import get_logger

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "ai" / "prompts"

_LOCAL_FILES: dict[str, str] = {
    "system": "system.md",
    "safety": "safety.md",
    "site-hints": "site_hints.md",
    "workbench": "experiment/workbench.md",
}

# Langfuse SDK can raise langfuse.api.Error (API/network), ValueError
# (invalid args), or OSError (DNS/socket). Catch all three for resilient
# fallback to local prompt files.
_LANGFUSE_ERRORS = (langfuse.api.Error, ValueError, OSError)


def _load_local(name: str) -> str:
    """Load a prompt from the local filesystem."""
    try:
        filename = _LOCAL_FILES[name]
    except KeyError:
        msg = f"Unknown prompt name: {name!r}. Known: {sorted(_LOCAL_FILES)}"
        raise ValueError(msg) from None
    path = _PROMPTS_DIR / filename
    return path.read_text()


def load_prompt(name: str, *, label: str = "production") -> str:
    """Load a prompt by name, trying Langfuse first with local fallback."""
    client = get_langfuse()
    if client is not None:
        try:
            prompt = client.get_prompt(name, label=label)
        except _LANGFUSE_ERRORS:
            logger.warning(
                "Langfuse prompt fetch failed, falling back to local",
                name=name,
                exc_info=True,
            )
        else:
            text: str = prompt.compile()
            logger.debug("Prompt loaded from Langfuse", name=name, label=label)
            return text

    text = _load_local(name)
    logger.debug("Prompt loaded from local file", name=name)
    return text


def seed_prompts() -> None:
    """Upload local prompt files to Langfuse if they don't exist yet."""
    client = get_langfuse()
    if client is None:
        return

    for name, filename in _LOCAL_FILES.items():
        try:
            client.get_prompt(name)
        except langfuse.api.Error:
            # Prompt does not exist — seed it. The broader _LANGFUSE_ERRORS
            # tuple is used for the create call since creation can fail for
            # various reasons (network, invalid args, etc.).
            text = (_PROMPTS_DIR / filename).read_text()
            try:
                client.create_prompt(
                    name=name,
                    prompt=text,
                    type="text",
                    labels=["production"],
                )
                logger.info("Seeded prompt to Langfuse", name=name)
            except _LANGFUSE_ERRORS:
                logger.warning("Failed to seed prompt", name=name, exc_info=True)
        else:
            logger.debug("Prompt already exists in Langfuse", name=name)
