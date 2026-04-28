from __future__ import annotations

from unittest.mock import MagicMock

from pathfinder.ai.agents._model_resolution import (
    SYSTEM_DEFAULT_MODEL_PER_COMMAND,
    resolve_specialist_model_id,
)
from pathfinder.ai.models.catalog import get_model_entry

VALID_HAIKU = "anthropic:claude-haiku-4-5"
VALID_SONNET = "anthropic:claude-sonnet-4-6"
INVALID = "nonsense:model"


def _user(defaults: dict[str, str] | None = None) -> MagicMock:
    user = MagicMock()
    user.specialist_model_defaults = defaults if defaults is not None else {}
    return user


async def test_resolve_returns_explicit_when_valid() -> None:
    user = _user(defaults={"validate": VALID_SONNET})
    resolved = await resolve_specialist_model_id(
        command="validate", user=user, explicit=VALID_HAIKU,
    )
    assert resolved == VALID_HAIKU


async def test_resolve_falls_back_to_sticky_default() -> None:
    user = _user(defaults={"validate": VALID_HAIKU})
    resolved = await resolve_specialist_model_id(
        command="validate", user=user, explicit=None,
    )
    assert resolved == VALID_HAIKU


async def test_resolve_falls_back_to_system_default() -> None:
    user = _user(defaults={})
    resolved = await resolve_specialist_model_id(
        command="research", user=user, explicit=None,
    )
    assert resolved == SYSTEM_DEFAULT_MODEL_PER_COMMAND["research"]
    assert get_model_entry(resolved) is not None


async def test_resolve_ignores_invalid_explicit() -> None:
    user = _user(defaults={"optimize": VALID_SONNET})
    resolved = await resolve_specialist_model_id(
        command="optimize", user=user, explicit=INVALID,
    )
    assert resolved == VALID_SONNET


async def test_resolve_ignores_invalid_sticky() -> None:
    user = _user(defaults={"validate": INVALID})
    resolved = await resolve_specialist_model_id(
        command="validate", user=user, explicit=None,
    )
    assert resolved == SYSTEM_DEFAULT_MODEL_PER_COMMAND["validate"]


def test_system_defaults_resolve_against_catalog() -> None:
    for model_id in SYSTEM_DEFAULT_MODEL_PER_COMMAND.values():
        assert get_model_entry(model_id) is not None
