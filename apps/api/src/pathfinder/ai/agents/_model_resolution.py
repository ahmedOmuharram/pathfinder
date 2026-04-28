from __future__ import annotations

from typing import Literal

from pathfinder.ai.models.catalog import (
    ModelEntry,
    get_model_entry,
    get_smallest_model,
)
from pathfinder.persistence.models import User
from pathfinder.platform.config import get_settings
from pathfinder.platform.types import ModelProvider

SpecialistCommand = Literal["validate", "research", "optimize"]


SYSTEM_DEFAULT_MODEL_PER_COMMAND: dict[SpecialistCommand, str] = {
    "validate": "openai:gpt-4.1-mini",
    "research": "openai:gpt-4.1-mini",
    "optimize": "openai:gpt-4.1-mini",
}


def resolve_orchestrator_model_entry(
    model_id: str | None, provider: ModelProvider | None,
) -> ModelEntry:
    """Pick the supervisor/compactor's model entry.

    Precedence: explicit catalog id -> explicit provider's smallest ->
    configured default provider's smallest. Same logic for supervisor
    and compactor so per-chat overrides + user prefs apply to both.
    """
    if model_id is not None:
        entry = get_model_entry(model_id)
        if entry is not None:
            return entry
    resolved_provider: ModelProvider = (
        provider or get_settings().default_provider
    )
    return get_smallest_model(resolved_provider)


def _system_default_for(command: SpecialistCommand) -> str:
    fallback = SYSTEM_DEFAULT_MODEL_PER_COMMAND[command]
    if get_model_entry(fallback) is not None:
        return fallback
    return get_smallest_model(get_settings().default_provider).id


async def resolve_specialist_model_id(
    *,
    command: SpecialistCommand,
    user: User,
    explicit: str | None,
) -> str:
    """Resolve a specialist's model id.

    Precedence: explicit override -> sticky user default -> system default
    per command. Invalid catalog ids at any tier are skipped.
    """
    if explicit is not None and get_model_entry(explicit) is not None:
        return explicit
    sticky = user.specialist_model_defaults.get(command)
    if sticky is not None and get_model_entry(sticky) is not None:
        return sticky
    return _system_default_for(command)
