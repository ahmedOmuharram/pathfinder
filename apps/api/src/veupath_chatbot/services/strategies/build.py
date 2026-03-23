"""Strategy build service: root resolution and result count lookup.

Step creation and strategy sync are now handled by step_creation.py and sync.py
respectively. This module retains root resolution and result count helpers.
"""

from dataclasses import dataclass
from typing import Protocol

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKStrategyDetails,
)
from veupath_chatbot.platform.logging import get_logger

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
) -> PlanStepNode:
    """Resolve the root step from the graph.

    :param graph: Strategy graph.
    :param explicit_root_step_id: Optional explicit root step ID override.
    :returns: The resolved root PlanStepNode.
    :raises RootResolutionError: When root cannot be determined.
    """

    if explicit_root_step_id:
        step = graph.get_step(explicit_root_step_id)
        if step:
            return step
        msg = f"Explicit root step '{explicit_root_step_id}' not found in graph."
        raise RootResolutionError(msg)

    if len(graph.roots) == 1:
        step = graph.get_step(next(iter(graph.roots)))
        if step:
            return step

    if len(graph.roots) > 1:
        msg = (
            f"Graph has {len(graph.roots)} subtree roots -- expected exactly 1 to build. "
            "Combine them first, or specify root_step_id."
        )
        raise RootResolutionError(
            msg,
            root_count=len(graph.roots),
        )

    msg = "No steps in graph. Create steps before building."
    raise RootResolutionError(msg)


# ---------------------------------------------------------------------------
# Step counts extraction
# ---------------------------------------------------------------------------


def extract_step_counts(
    strategy_info: WDKStrategyDetails,
    compiled_map: dict[str, int],
) -> tuple[dict[str, int | None], int | None]:
    """Extract per-step result counts from a WDK strategy payload.

    :param strategy_info: Typed WDK strategy details (from ``api.get_strategy``).
    :param compiled_map: Mapping of local_step_id -> wdk_step_id.
    :returns: Tuple of (step_counts dict, root_count).
    """
    step_counts: dict[str, int | None] = {}
    root_count: int | None = None

    wdk_to_local = {v: k for k, v in compiled_map.items()}

    for wdk_id_str, step in strategy_info.steps.items():
        try:
            wdk_id_int = int(wdk_id_str)
        except ValueError, TypeError:
            continue
        local_id = wdk_to_local.get(wdk_id_int)
        if local_id:
            step_counts[local_id] = step.estimated_size

    root_local = wdk_to_local.get(strategy_info.root_step_id)
    if root_local:
        root_count = step_counts.get(root_local)

    return step_counts, root_count


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
