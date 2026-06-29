from __future__ import annotations

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.build_outcome import BuildOutcome, StepPushFailure
from pathfinder.services.strategies.spec_build import _node_results
from pathfinder.services.strategies.sync_state import WDKSyncState


def test_node_results_maps_counts_and_step_ids() -> None:
    leaf1 = StrategyStepNode(search_name="GenesWithSignalPeptide")
    leaf2 = StrategyStepNode(search_name="GenesByTransmembraneDomains")
    sync = WDKSyncState()
    sync.wdk_step_ids = {leaf1.id: 100, leaf2.id: 200}
    outcome = BuildOutcome(counts={leaf1.id: 437, leaf2.id: 0})

    results = {r.node_id: r for r in _node_results([leaf1, leaf2], sync, outcome)}

    assert results[leaf1.id].status == "ok"
    assert results[leaf1.id].count == 437
    assert results[leaf1.id].wdk_step_id == 100
    assert results[leaf1.id].search_name == "GenesWithSignalPeptide"
    assert results[leaf2.id].status == "zero"


def test_node_results_marks_failed_with_error() -> None:
    leaf = StrategyStepNode(search_name="GenesByTransmembraneDomains")
    outcome = BuildOutcome(
        failed_steps=[
            StepPushFailure(
                step_id=leaf.id,
                search_name="GenesByTransmembraneDomains",
                error="bad param",
            )
        ]
    )

    results = _node_results([leaf], WDKSyncState(), outcome)

    assert results[0].status == "failed"
    assert results[0].error == "bad param"
    assert results[0].count is None
