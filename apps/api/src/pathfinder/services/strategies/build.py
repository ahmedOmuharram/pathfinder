"""Strategy build service: root resolution and result count lookup.

Step creation and strategy sync are now handled by step_creation.py and sync.py
respectively. This module retains root resolution and result count helpers.
"""

from dataclasses import dataclass
from typing import Protocol

from pathfinder.domain.strategy.graph_model import StrategyStep
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKStrategyDetails,
)
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Protocols -- I/O boundaries
# ---------------------------------------------------------------------------


class StepCountAPI(Protocol):
    """Protocol for result count lookup."""

    async def get_strategy(self, strategy_id: int) -> WDKStrategyDetails: ...

    async def get_step_count(self, step_id: int) -> int: ...


class SiteInfoLike(Protocol):
    """Protocol for site metadata needed by the build service."""

    def strategy_url(
        self, strategy_id: int, root_step_id: int | None = None
    ) -> str: ...


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class StepCountResult:
    """Outcome of a step count lookup."""

    step_id: int
    count: int


# ---------------------------------------------------------------------------
# Root resolution
# ---------------------------------------------------------------------------


class RootResolutionError(Exception):
    """Raised when a single root step cannot be resolved from the graph."""

    def __init__(self, message: str, root_count: int = 0) -> None:
        super().__init__(message)
        self.root_count = root_count


def resolve_root_step(
    graph: StrategyGraph,
    explicit_root_step_id: str | None,
) -> StrategyStep:
    """Resolve the root step from the graph.

    :param graph: Strategy graph.
    :param explicit_root_step_id: Optional explicit root step ID override.
    :returns: The resolved root StrategyStepNode.
    :raises RootResolutionError: When root cannot be determined.
    """

    if explicit_root_step_id:
        step = graph.get_step(explicit_root_step_id)
        if step:
            return step
        msg = f"Explicit root step '{explicit_root_step_id}' not found in graph."
        raise RootResolutionError(msg)

    # Several roots is an ordinary editing state: a search added but not yet
    # combined, or a branch just detached. The WDK strategy is the primary
    # component; the rest persist locally as detached roots and are not pushed
    # (WDK rejects a step that has inputs but no strategy).
    primary_id = graph.primary_root_id()
    if primary_id is not None:
        step = graph.get_step(primary_id)
        if step:
            return step

    msg = "No steps in graph. Create steps before building."
    raise RootResolutionError(msg)


# ---------------------------------------------------------------------------
# Result count lookup
# ---------------------------------------------------------------------------


async def get_estimated_size(
    api: StepCountAPI,
    wdk_step_id: int,
    wdk_strategy_id: int | None = None,
) -> StepCountResult:
    """Get the result count for a built WDK step.

    First tries to read ``estimatedSize`` from the strategy payload (cheaper),
    then falls back to a direct step count query.

    :raises TypeError: If strategy payload is malformed.
    :raises Exception: On WDK API errors (propagated to caller).
    """
    if wdk_strategy_id is not None:
        strategy = await api.get_strategy(wdk_strategy_id)
        step = strategy.steps.get(str(wdk_step_id))
        if step is not None and step.estimated_size is not None:
            return StepCountResult(step_id=wdk_step_id, count=step.estimated_size)

    count = await api.get_step_count(wdk_step_id)
    return StepCountResult(step_id=wdk_step_id, count=count)


# ---------------------------------------------------------------------------
# Convenience entry points (resolve integrations internally)
# ---------------------------------------------------------------------------


async def get_estimated_size_for_site(
    site_id: str,
    wdk_step_id: int,
    wdk_strategy_id: int | None = None,
) -> StepCountResult:
    """Get result count using factory-resolved API.

    This is the entry point for the AI tool layer.
    """
    api = get_strategy_api(site_id)
    return await get_estimated_size(api, wdk_step_id, wdk_strategy_id)
