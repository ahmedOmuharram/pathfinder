"""Typed accessors for per-turn metadata on :class:`AgentDeps`.

``AgentDeps.turn_metadata`` is a :class:`JSONObject` — intentionally loose
because different layers write different signals into it.  Downstream
consumers that need a specific signal should go through a typed reader
here instead of scattering ``dict.get`` / ``isinstance`` checks at call
sites.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from pathfinder.domain.strategy.plan import FailureKind
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject


class _TurnMetadataEnvelope(CamelModel):
    """Typed view of the subset of ``turn_metadata`` this module owns.

    Serialises ``failure_kind`` as the camelCase key ``failureKind`` so
    producers can set ``turn_metadata["failureKind"] = ...`` naturally.
    ``extra="ignore"`` keeps the envelope forward-compatible with new
    metadata slots owned by other modules.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    failure_kind: FailureKind | None = Field(default=None)


def read_failure_kind(turn_metadata: JSONObject) -> FailureKind | None:
    """Return the typed failure classification, or ``None`` if unset/invalid.

    Unknown string values yield ``None`` (fail-closed) rather than raising so
    that producers emitting future values do not crash the phase driver.
    Only exact :class:`FailureKind` members are honoured.
    """
    try:
        envelope = _TurnMetadataEnvelope.model_validate(turn_metadata)
    except ValidationError:
        return None
    return envelope.failure_kind


def write_failure_kind(turn_metadata: JSONObject, kind: FailureKind) -> None:
    """Store a typed :class:`FailureKind` on the shared ``turn_metadata`` dict.

    Uses the envelope's camelCase alias so the on-the-wire key matches the
    convention used by :func:`read_failure_kind` and other producers.
    """
    payload = _TurnMetadataEnvelope(failure_kind=kind).model_dump(
        by_alias=True, mode="json", exclude_none=True
    )
    turn_metadata.update(payload)
