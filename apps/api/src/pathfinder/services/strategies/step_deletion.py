"""Step deletion service with connected graph semantics.

Wraps StrategyGraph.delete_step_connected with WDK metadata cleanup
(wdk_step_ids, step_counts, step_validations, wdk_push_errors).
"""

from dataclasses import dataclass

from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.services.strategies.sync_state import WDKSyncState


@dataclass
class StepDeletionResult:
    """Result of a connected step deletion."""

    deleted_ids: list[str]


async def delete_step_connected(
    graph: StrategyGraph,
    sync_state: WDKSyncState,
    step_id: str,
) -> StepDeletionResult:
    """Delete a step using connected semantics and clean up WDK metadata.

    Delegates tree manipulation to StrategyGraph.delete_step_connected,
    then cleans up associated WDK state for all deleted steps.

    :param graph: The strategy graph.
    :param sync_state: WDK synchronization state.
    :param step_id: ID of the step to delete.
    :returns: StepDeletionResult with the list of deleted step IDs.
    """
    deleted_ids = graph.delete_step_connected(step_id)
    for sid in deleted_ids:
        sync_state.wdk_step_ids.pop(sid, None)
        sync_state.step_counts.pop(sid, None)
        sync_state.step_validations.pop(sid, None)
        sync_state.wdk_push_errors.pop(sid, None)
    return StepDeletionResult(deleted_ids=deleted_ids)
