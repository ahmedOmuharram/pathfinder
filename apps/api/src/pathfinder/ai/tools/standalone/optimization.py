"""Standalone optimization tools for pydantic-ai agents.

Provides:
- ``optimize_search_parameters`` — optimise search parameters against control
  gene lists. Durable: the real work runs on the verification worker via
  ``@durable_tool``; the graph suspends with ``interrupt()`` while trials run
  and per-trial progress streams back through ``task_progress``.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.durable import durable_tool
from pathfinder.ai.tools.standalone._optimization_models import (
    OptimizationControls,
    OptimizationSettings,
    OptimizationTarget,
)

_DEFAULT_SETTINGS = OptimizationSettings()


@durable_tool(
    tool_name="optimize_search_parameters",
    estimated_duration_seconds=900,
)
async def optimize_search_parameters(
    ctx: RunContext[AgentDeps],
    target: OptimizationTarget,
    controls: OptimizationControls,
    settings: OptimizationSettings = _DEFAULT_SETTINGS,
) -> dict[str, Any]:
    """Optimise search parameters against positive/negative control gene lists.

    Durable. Runs up to ``settings.budget`` trials on the verification
    worker; each trial calls WDK. The graph suspends on ``interrupt()``
    while the optimiser runs and resumes with the result dict (matching
    :class:`OptimizationResult`'s ``model_dump(by_alias=True)`` shape).

    This is a long-running operation. Always confirm the plan with the user
    before calling; the verification toolset carries ``requires_approval=True``
    so the SDK emits a ``ToolApprovalRequestChunk`` first.

    Args:
        target: Target search to optimise.
        controls: Control sets for scoring.
        settings: Optimisation hyperparameters.
    """
    del ctx, target, controls, settings
    msg = "optimize_search_parameters runs on the worker via @durable_tool"
    raise NotImplementedError(msg)
