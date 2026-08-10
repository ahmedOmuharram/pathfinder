"""A dependent param's vocabulary must be read under the parents the spec has
already bound, not under the search's defaults.

Observed on the DeRisi time-course criterion. FRAME bound
``profileset_generic = "DeRisi 3D7 Smoothed"``, then called
``get_parameter_options`` for ``samples_percentile_generic`` with no
``context_values``. WDK answered with the DEFAULT profileset's vocabulary --
``DeRisi HB3 Smoothed`` -- and the three time courses genuinely differ:

    DeRisi 3D7 Smoothed   46 leaves, no "47 Hour"/"48 Hour"
    DeRisi HB3 Smoothed   46 leaves, no "23 Hour"/"29 Hour"
    DeRisi Dd2 Smoothed   45 leaves, no "8 Hour"/"44 Hour"/"48 Hour"

The model asked for hours 20-32, was shown HB3's list, correctly observed that
23 and 29 were missing, and reported the criterion unsatisfiable. It was right
about what it saw. The tool showed it the wrong dataset.

The bound value is already in the draft spec, so nothing needs to be asked or
guessed -- it just has to be carried into the read.
"""

from __future__ import annotations

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.domain.parameters.values import (
    MultiPickValue,
    SinglePickValue,
)
from pathfinder.domain.strategy.operational_spec import Criterion


def _derisi_criterion() -> Criterion:
    return Criterion(
        id="timecourse",
        text="trophozoite stage expression",
        search_name="GenesByMicroarrayDerisi",
        resolved_params={
            "profileset_generic": SinglePickValue(value="DeRisi 3D7 Smoothed"),
            "channel": SinglePickValue(value="Channel 1"),
        },
    )


class TestResolvedParamsFor:
    def test_returns_the_bound_parents_of_that_search(self) -> None:
        state = AgentToolState()
        state.frame_set_criterion(_derisi_criterion())

        assert state.resolved_params_for("GenesByMicroarrayDerisi") == {
            "profileset_generic": SinglePickValue(value="DeRisi 3D7 Smoothed"),
            "channel": SinglePickValue(value="Channel 1"),
        }

    def test_is_empty_for_a_search_no_criterion_uses(self) -> None:
        state = AgentToolState()
        state.frame_set_criterion(_derisi_criterion())

        assert state.resolved_params_for("GenesByInterproDomain") == {}

    def test_is_empty_when_nothing_is_bound(self) -> None:
        assert AgentToolState().resolved_params_for("GenesByMicroarrayDerisi") == {}

    def test_does_not_leak_across_searches(self) -> None:
        state = AgentToolState()
        state.frame_set_criterion(_derisi_criterion())
        state.frame_set_criterion(
            Criterion(
                id="domain",
                text="kinase domain",
                search_name="GenesByInterproDomain",
                resolved_params={
                    "domain_database": SinglePickValue(value="PFAM"),
                },
            )
        )

        derisi = state.resolved_params_for("GenesByMicroarrayDerisi")

        assert "domain_database" not in derisi

    def test_merges_criteria_that_share_a_search(self) -> None:
        # Two criteria can legitimately bind the same search (e.g. an up- and a
        # down-regulated arm). Their parents together are the context.
        state = AgentToolState()
        state.frame_set_criterion(
            Criterion(
                id="up",
                text="induced",
                search_name="GenesByMicroarrayDerisi",
                resolved_params={
                    "profileset_generic": SinglePickValue(value="DeRisi 3D7 Smoothed")
                },
            )
        )
        state.frame_set_criterion(
            Criterion(
                id="down",
                text="repressed",
                search_name="GenesByMicroarrayDerisi",
                resolved_params={"channel": SinglePickValue(value="Channel 2")},
            )
        )

        merged = state.resolved_params_for("GenesByMicroarrayDerisi")

        assert set(merged) == {"profileset_generic", "channel"}

    def test_ignores_criteria_with_no_search_bound(self) -> None:
        state = AgentToolState()
        state.frame_set_criterion(
            Criterion(id="vague", text="something", search_name="")
        )

        assert state.resolved_params_for("") == {}

    def test_carries_multi_pick_values_unchanged(self) -> None:
        state = AgentToolState()
        state.frame_set_criterion(
            Criterion(
                id="c",
                text="t",
                search_name="S",
                resolved_params={
                    "samples": MultiPickValue(values=["20 Hour", "21 Hour"])
                },
            )
        )

        assert state.resolved_params_for("S") == {
            "samples": MultiPickValue(values=["20 Hour", "21 Hour"])
        }
