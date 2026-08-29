"""The workspace shows FRAME the values it is being asked to preserve.

A criterion rendered as a label and a search name has to be re-bound from its
own 60-character text, which re-derives every parameter the text does not
state. The values are already bound, so the workspace prints them.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from pathfinder.ai.agents.strategy_instructions import pinned_frame_workspace
from pathfinder.domain.parameters.values import (
    MultiPickValue,
    NumberValue,
    SinglePickValue,
)
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OpenSlot,
    OperationalSpec,
)


def _ctx(spec: OperationalSpec) -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.agent_state.operational_spec_draft = spec
    return ctx


def _bound_spec() -> OperationalSpec:
    return OperationalSpec(
        goal="find kinases",
        criteria=[
            Criterion(
                id="c_expr",
                text="genes in the top decile of expression",
                search_name="GenesByRNASeqEvidence",
                resolved_params={
                    "min_expression_percentile": NumberValue(value=90),
                    "any_or_all": SinglePickValue(value="any"),
                    "organism": MultiPickValue(values=["Plasmodium"]),
                },
            )
        ],
    )


def test_workspace_renders_bound_values() -> None:
    rendered = pinned_frame_workspace(_ctx(_bound_spec()))

    assert rendered is not None
    assert "min_expression_percentile=90" in rendered


def test_workspace_renders_a_multi_pick_in_wire_form() -> None:
    rendered = pinned_frame_workspace(_ctx(_bound_spec()))

    assert rendered is not None
    assert 'organism=["Plasmodium"]' in rendered
    assert "any_or_all=any" in rendered


def test_workspace_says_the_values_are_preserved_unless_the_request_changes_them() -> (
    None
):
    rendered = pinned_frame_workspace(_ctx(_bound_spec()))

    assert rendered is not None
    assert "preserved unless the request changes them" in rendered


def test_workspace_still_names_the_open_slots() -> None:
    spec = OperationalSpec(
        goal="g",
        criteria=[
            Criterion(
                id="c_open",
                text="a criterion with an unanswered parameter",
                search_name="GenesByRNASeqEvidence",
                open_params=[OpenSlot(criterion_id="c_open", param_name="profileset")],
            )
        ],
    )

    rendered = pinned_frame_workspace(_ctx(spec))

    assert rendered is not None
    assert "profileset" in rendered


def test_an_empty_draft_renders_nothing() -> None:
    assert pinned_frame_workspace(_ctx(OperationalSpec(goal="g"))) is None
