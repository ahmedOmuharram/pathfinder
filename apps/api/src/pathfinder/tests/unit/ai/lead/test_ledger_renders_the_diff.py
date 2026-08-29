"""The ledger reports what the turn did to the spec, not just how big it is.

"criteria 3" cannot tell the Lead whether the third criterion is the one the
turn started with. The Lead's "preserved" sentence is written from this.
"""

from __future__ import annotations

from uuid import uuid4

from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.domain.parameters.values import NumberValue
from pathfinder.domain.strategy.operational_spec import Criterion, OperationalSpec


def _criterion(cid: str, percentile: float | None = None) -> Criterion:
    params = {} if percentile is None else {"pct": NumberValue(value=percentile)}
    return Criterion(
        id=cid, text=f"criterion {cid}", search_name=f"By{cid}", resolved_params=params
    )


def _state(
    before: OperationalSpec | None, after: OperationalSpec | None
) -> PipelineState:
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        domain=StrategyDomainState(
            operational_spec=after,
            spec_before_turn=before,
        ),
    )


def _spec(*criteria: Criterion) -> OperationalSpec:
    return OperationalSpec(goal="g", criteria=list(criteria))


def test_ledger_renders_the_diff() -> None:
    before = _spec(_criterion("a"), _criterion("b"), _criterion("c", 80))
    after = _spec(_criterion("a"), _criterion("b"), _criterion("c", 90))

    summary = derive_ledger(_state(before, after), None).render_summary()

    assert "kept 2, changed 1, added 0, dropped 0" in summary


def test_the_diff_names_a_dropped_criterion() -> None:
    before = _spec(_criterion("a"), _criterion("b"))
    after = _spec(_criterion("a"))

    ledger = derive_ledger(_state(before, after), None)

    spec_diff = ledger.frame.spec_diff()
    assert spec_diff is not None
    assert spec_diff.dropped_ids() == ["b"]


def test_a_fresh_turn_has_no_diff() -> None:
    ledger = derive_ledger(_state(None, _spec(_criterion("a"))), None)

    assert ledger.frame.spec_diff() is None


def test_the_entry_spec_does_not_reach_the_wire() -> None:
    """The ledger chunk carries the comparison, never a second whole spec."""
    before = _spec(_criterion("a"), _criterion("b"))
    ledger = derive_ledger(_state(before, _spec(_criterion("a"))), None)

    payload = ledger.model_dump(by_alias=True, mode="json", exclude_none=True)

    assert "specBeforeTurn" not in payload["frame"]
    assert payload["frame"]["diff"]["droppedCount"] == 1
