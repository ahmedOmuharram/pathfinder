"""Registry mapping durable tool names to their worker-side implementations.

The worker receives a task payload with a ``tool_name`` and looks up the real
callable here. Phase 5 fills this registry; Phase 4 ships the scaffolding.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

ToolImpl = Callable[..., Awaitable[Any]]

TOOL_REGISTRY: dict[str, ToolImpl] = {}


def register_tool(name: str, impl: ToolImpl) -> None:
    """Register a durable tool implementation by name."""
    TOOL_REGISTRY[name] = impl
