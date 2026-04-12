"""Prompt loading helpers for the AI agent."""

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256

from pathfinder.platform.langfuse.prompts import LoadedPrompt, load_prompt_result


@dataclass(frozen=True)
class PromptBundle:
    """Combined prompt text plus prompt-component metadata."""

    text: str
    prompts: tuple[LoadedPrompt, ...]

    def langfuse_metadata(self) -> dict[str, str]:
        """Return compact filterable metadata for Langfuse observations."""
        bundle_hash = sha256(self.text.encode("utf-8")).hexdigest()
        metadata = {
            "prompt_bundle": ",".join(
                f"{prompt.name}@{prompt.version if prompt.version is not None else prompt.source}"
                for prompt in self.prompts
            ),
            "prompt_sources": ",".join(prompt.source for prompt in self.prompts),
            "prompt_bundle_hash": bundle_hash,
        }
        for prompt in self.prompts:
            key = prompt.name.replace("-", "_")
            metadata[f"{key}_prompt_source"] = prompt.source
            metadata[f"{key}_prompt_label"] = prompt.label
            if prompt.version is not None:
                metadata[f"{key}_prompt_version"] = str(prompt.version)
        return metadata


@lru_cache(maxsize=2)
def load_system_prompt_bundle(*, include_site_hints: bool = True) -> PromptBundle:
    """Load and combine the unified system prompt with prompt metadata."""
    parts = [
        load_prompt_result("system"),
        load_prompt_result("safety"),
    ]
    if include_site_hints:
        parts.append(load_prompt_result("site-hints"))
    return PromptBundle(
        text="\n\n---\n\n".join(prompt.text for prompt in parts),
        prompts=tuple(parts),
    )


def load_system_prompt(*, include_site_hints: bool = True) -> str:
    """Load and combine the unified system prompt.

    :param include_site_hints: When False, skip site_hints.md to save ~400
        tokens on continuation turns where the model already has site context.
    """
    return load_system_prompt_bundle(include_site_hints=include_site_hints).text
