"""Step deletion service with connected graph semantics.

Wraps StrategyGraph.delete_step_connected with WDK metadata cleanup
(wdk_step_ids, step_counts, step_validations, wdk_push_errors).
"""

from dataclasses import dataclass

from pathfinder.domain.strategy.session import StrategyGraph


@dataclass
class StepDeletionResult:
    """Result of a connected step deletion."""

    deleted_ids: list[str]


async def delete_step_connected(
    graph: StrategyGraph,
    step_id: str,
) -> StepDeletionResult:
    """Delete a step using connected semantics and clean up WDK metadata.

    Delegates tree manipulation to StrategyGraph.delete_step_connected,
    then cleans up associated WDK state for all deleted steps.

    :param graph: The strategy graph.
    :param step_id: ID of the step to delete.
    :returns: StepDeletionResult with the list of deleted step IDs.
    """
    deleted_ids = graph.delete_step_connected(step_id)
    for sid in deleted_ids:
        graph.wdk_step_ids.pop(sid, None)
        graph.step_counts.pop(sid, None)
        graph.step_validations.pop(sid, None)
        graph.wdk_push_errors.pop(sid, None)
    return StepDeletionResult(deleted_ids=deleted_ids)
