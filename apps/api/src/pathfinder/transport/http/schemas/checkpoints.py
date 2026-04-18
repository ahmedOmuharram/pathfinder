from __future__ import annotations

from typing import Any

from pydantic import Field

from pathfinder.platform.pydantic_base import CamelModel


class ForkRequest(CamelModel):
    """Body for ``POST /chats/{conversation_id}/fork``.

    ``state_override`` defaults to an empty dict — the absence of overrides
    still produces a fresh checkpoint that becomes a child of
    ``from_checkpoint_id``. ``as_node`` is forwarded to
    ``graph.aupdate_state(..., as_node=...)`` and decides which node
    "owns" the synthetic write.
    """

    from_checkpoint_id: str
    state_override: dict[str, Any] = Field(default_factory=dict)
    as_node: str | None = None


class ForkResponse(CamelModel):
    new_checkpoint_id: str


class LabelRequest(CamelModel):
    label: str | None = None
    pinned: bool = False


class LabelRow(CamelModel):
    checkpoint_id: str
    label: str | None
    pinned: bool
