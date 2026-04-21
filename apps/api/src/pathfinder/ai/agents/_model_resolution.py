from __future__ import annotations

from pathfinder.ai.models.catalog import (
    ModelEntry,
    get_model_entry,
    get_smallest_model,
)
from pathfinder.platform.config import get_settings
from pathfinder.platform.types import ModelProvider


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
