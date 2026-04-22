"""Per-user preferences persisted server-side on the ``users`` row.

Fields:

* ``supervisor_model_id`` — catalog id (e.g. ``anthropic/claude-sonnet-4-5``)
  overriding the orchestrator's default model. ``None`` = auto (use the
  smallest model of the configured default provider).
* ``pipeline_config`` — per-phase ``{modelId, reasoningEffort}`` overrides,
  plus the provider/tier the user picked. ``None`` = use phase-agent
  defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.models.catalog import get_model_entry
from pathfinder.persistence.models import Conversation, User
from pathfinder.platform.pipeline import (
    PhaseConfigPayload,
    PipelineConfigPayload,
)
from pathfinder.platform.types import JSONObject, PipelinePhase


@dataclass(frozen=True)
class UserPreferences:
    supervisor_model_id: str | None
    pipeline_config: PipelineConfigPayload | None = None


class UnknownModelError(ValueError):
    """Raised when a supervisor_model_id or phase modelId is not in the catalog."""


def _parse_pipeline_config(raw: Any) -> PipelineConfigPayload | None:
    if raw is None:
        return None
    if isinstance(raw, PipelineConfigPayload):
        return raw
    try:
        return PipelineConfigPayload.model_validate(raw)
    except ValidationError as exc:
        msg = f"invalid pipeline_config: {exc}"
        raise UnknownModelError(msg) from exc


def _validate_pipeline_catalog(payload: PipelineConfigPayload) -> None:
    for phase, cfg in payload.phases.items():
        if get_model_entry(cfg.model_id) is None:
            msg = f"unknown modelId for phase {phase!r}: {cfg.model_id}"
            raise UnknownModelError(msg)


async def get_preferences(session: AsyncSession, user_id: UUID) -> UserPreferences:
    row = await session.execute(
        select(User.supervisor_model_id, User.pipeline_config).where(
            User.id == user_id,
        ),
    )
    result = row.one_or_none()
    if result is None:
        return UserPreferences(supervisor_model_id=None, pipeline_config=None)
    supervisor_model_id, pipeline_config = result
    parsed = _parse_pipeline_config(pipeline_config) if pipeline_config else None
    return UserPreferences(
        supervisor_model_id=supervisor_model_id, pipeline_config=parsed,
    )


async def resolve_supervisor_model_id(
    session: AsyncSession, *, user_id: UUID, conversation_id: UUID,
) -> str | None:
    """Conversation override → user default → None (auto)."""
    result = await session.execute(
        select(
            Conversation.supervisor_model_id,
            User.supervisor_model_id,
        )
        .join(User, User.id == Conversation.user_id)
        .where(Conversation.id == conversation_id, User.id == user_id),
    )
    row = result.one_or_none()
    if row is None:
        return None
    conv_pref: str | None = row[0]
    user_pref: str | None = row[1]
    return conv_pref if conv_pref is not None else user_pref


async def resolve_phase_model(
    session: AsyncSession, *, user_id: UUID, phase: PipelinePhase,
) -> str | None:
    """Return the user's override model_id for a phase, or None for default."""
    row = await session.scalar(
        select(User.pipeline_config).where(User.id == user_id),
    )
    if row is None:
        return None
    parsed = _parse_pipeline_config(row)
    if parsed is None:
        return None
    cfg = parsed.phases.get(phase)
    return cfg.model_id if cfg is not None else None


async def apply_patch(
    session: AsyncSession, user_id: UUID, patch: dict[str, Any],
) -> UserPreferences:
    """Apply a partial update. Only keys present in ``patch`` are written."""
    values: dict[str, Any] = {}
    if "supervisor_model_id" in patch:
        value = patch["supervisor_model_id"]
        if value is not None:
            if not isinstance(value, str):
                msg = "supervisor_model_id must be a string or null"
                raise UnknownModelError(msg)
            if get_model_entry(value) is None:
                msg = f"unknown supervisor_model_id: {value}"
                raise UnknownModelError(msg)
        values["supervisor_model_id"] = value
    if "pipeline_config" in patch:
        raw = patch["pipeline_config"]
        if raw is None:
            values["pipeline_config"] = None
        else:
            parsed = _parse_pipeline_config(raw)
            if parsed is None:
                values["pipeline_config"] = None
            else:
                _validate_pipeline_catalog(parsed)
                values["pipeline_config"] = cast(
                    "JSONObject",
                    parsed.model_dump(by_alias=True, mode="json"),
                )
    if values:
        await session.execute(
            update(User).where(User.id == user_id).values(**values),
        )
        await session.commit()
    return await get_preferences(session, user_id)


def phase_config_from_dict(
    raw: Any,
) -> dict[PipelinePhase, PhaseConfigPayload]:
    """Build a typed per-phase config map from a JSON dict (API input)."""
    payload = _parse_pipeline_config(raw)
    return dict(payload.phases) if payload is not None else {}
