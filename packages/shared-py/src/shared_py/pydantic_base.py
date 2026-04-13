"""Canonical Pydantic base for PathFinder wire-facing shared models.

`CamelModel` serializes to camelCase aliases and accepts snake_case input —
matches the JSON convention used across the AI SDK UI Message Stream protocol
and the TypeScript frontend.

Note: `pathfinder.platform.pydantic_base` also defines a `CamelModel` for
backend-only use. That sibling does NOT set `extra="ignore"` because internal
models benefit from strict validation. The `shared_py` base DOES set
`extra="ignore"` because wire-facing payloads need to tolerate additive
protocol changes without breaking old clients.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Wire-facing model: camelCase aliases, tolerates extra fields."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )
