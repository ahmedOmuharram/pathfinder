"""Langfuse-backed prompt management with local file fallback.

Prompt lifecycle:
1. Try Langfuse SDK (versioned, A/B testable, rollbackable from dashboard)
2. Fall back to local .md files (always works, even without Langfuse)
3. On first Langfuse startup, seed prompts from local files if missing
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import langfuse.api
from langfuse.api.commons import errors as langfuse_errors

from pathfinder.platform.langfuse.client import get_langfuse
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "ai" / "prompts"

PromptSource = Literal["langfuse", "local"]


@dataclass(frozen=True)
class LoadedPrompt:
    """Resolved prompt text plus the metadata Langfuse exposes for it."""

    name: str
    text: str
    label: str
    source: PromptSource
    version: int | None = None

_LOCAL_FILES: dict[str, str] = {
    "system": "system.md",
    "safety": "safety.md",
    "site-hints": "site_hints.md",
    "workbench": "experiment/workbench.md",
}

# The current Langfuse SDK raises multiple error classes across namespaces.
# In particular, missing prompts use langfuse_errors.NotFoundError rather than
# langfuse.api.Error. Treat all of them as recoverable so prompt loading can
# fall back to local files instead of crashing startup.
_LANGFUSE_ERRORS = (
    langfuse.api.Error,
    langfuse_errors.Error,
    langfuse_errors.NotFoundError,
    langfuse_errors.UnauthorizedError,
    langfuse_errors.AccessDeniedError,
    langfuse_errors.MethodNotAllowedError,
    ValueError,
    OSError,
)


def _load_local(name: str, *, label: str) -> LoadedPrompt:
    """Load a prompt from the local filesystem."""
    try:
        filename = _LOCAL_FILES[name]
    except KeyError:
        msg = f"Unknown prompt name: {name!r}. Known: {sorted(_LOCAL_FILES)}"
        raise ValueError(msg) from None
    path = _PROMPTS_DIR / filename
    return LoadedPrompt(
        name=name,
        text=path.read_text(),
        label=label,
        source="local",
    )


def load_prompt_result(name: str, *, label: str = "production") -> LoadedPrompt:
    """Load a prompt plus its source/version metadata."""
    client = get_langfuse()
    if client is not None:
        try:
            prompt = client.get_prompt(name, label=label)
        except langfuse_errors.NotFoundError:
            logger.info(
                "Langfuse prompt not found, falling back to local",
                name=name,
                label=label,
            )
        except _LANGFUSE_ERRORS:
            logger.warning(
                "Langfuse prompt fetch failed, falling back to local",
                name=name,
                exc_info=True,
            )
        else:
            text: str = prompt.compile()
            logger.debug("Prompt loaded from Langfuse", name=name, label=label)
            return LoadedPrompt(
                name=name,
                text=text,
                label=label,
                source="langfuse",
                version=getattr(prompt, "version", None),
            )

    text = _load_local(name, label=label)
    logger.debug("Prompt loaded from local file", name=name)
    return text


def load_prompt(name: str, *, label: str = "production") -> str:
    """Load a prompt by name, trying Langfuse first with local fallback."""
    return load_prompt_result(name, label=label).text


def seed_prompts() -> None:
    """Upload local prompt files to Langfuse if they don't exist yet."""
    client = get_langfuse()
    if client is None:
        return

    for name, filename in _LOCAL_FILES.items():
        try:
            client.get_prompt(name)
        except langfuse_errors.NotFoundError:
            # Prompt does not exist yet — seed it from the local file.
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
        except _LANGFUSE_ERRORS:
            logger.warning(
                "Langfuse prompt existence check failed; skipping seed",
                name=name,
                exc_info=True,
            )
        else:
            logger.debug("Prompt already exists in Langfuse", name=name)
