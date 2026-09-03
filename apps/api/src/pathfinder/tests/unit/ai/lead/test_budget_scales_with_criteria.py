"""The phase ceiling follows the size of the problem the pass must solve.

A constant is generous for a two-criterion request and impossible for a
nine-criterion one. The Lead declares the size it reads in the goal, and the
thread's own statements are the floor under that declaration.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.sub_agent_tools import (
    CALLS_PER_CRITERION,
    MAX_CRITERIA_FLOOR,
    MAX_PHASE_TOOL_CALLS,
    MIN_PHASE_TOOL_CALLS,
    criteria_floor,
    phase_usage_limits,
)
from pathfinder.domain.strategy.constraints import (
    Constraint,
    ConstraintKind,
    ConstraintSource,
)
from pathfinder.domain.strategy.operational_spec import Criterion, OperationalSpec


def _state() -> PipelineState:
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="Find the kinases.",
    )


def _spec(count: int) -> OperationalSpec:
    return OperationalSpec(
        goal="find the kinases",
        criteria=[
            Criterion(id=f"c{i}", text=f"criterion {i}") for i in range(1, count + 1)
        ],
    )


def _requirement(
    kind: ConstraintKind,
    label: str,
    value: str,
) -> Constraint:
    return Constraint(
        kind=kind,
        label=label,
        requested_value=value,
        source=ConstraintSource.USER_EXPLICIT,
    )


def _eight_criterion_thread() -> list[Constraint]:
    """Twelve requirements naming eight criteria, as a clarified thread holds."""
    return [
        _requirement(ConstraintKind.ORGANISM, "organism", "Plasmodium falciparum"),
        _requirement(ConstraintKind.DATA_TYPE, "phylogenetic profile", "orthology"),
        _requirement(
            ConstraintKind.COMBINATION,
            "trophozoite evidence",
            "high expression AND mass spec evidence",
        ),
        _requirement(ConstraintKind.DATA_TYPE, "variation dataset", "SNP calls"),
        _requirement(ConstraintKind.PERCENTILE, "high expression", "top 10%"),
        _requirement(ConstraintKind.STATISTICAL_THRESHOLD, "dN/dS", "> 1.0"),
        _requirement(
            ConstraintKind.COMBINATION,
            "kinase identification",
            "domain OR ec number OR go term OR annotation",
        ),
        _requirement(
            ConstraintKind.OTHER,
            "non-syntenic orthologs",
            "transform to orthologs",
        ),
        _requirement(ConstraintKind.DATA_TYPE, "mass spec evidence", "proteomics"),
        _requirement(ConstraintKind.STATISTICAL_THRESHOLD, "mass spec score", ">= 2"),
        _requirement(ConstraintKind.DATA_TYPE, "expression dataset", "trophozoite"),
        _requirement(ConstraintKind.STATISTICAL_THRESHOLD, "SNP count", ">= 5"),
    ]


class TestTheFloorComesFromTheThread:
    def test_an_empty_thread_leaves_the_declaration_alone(self) -> None:
        assert criteria_floor(_state()) == 0

    def test_the_spec_the_turn_started_from_sets_the_floor(self) -> None:
        state = _state()
        state.domain.spec_before_turn = _spec(8)
        assert criteria_floor(state) == 8

    def test_the_spec_the_thread_holds_sets_the_floor(self) -> None:
        state = _state()
        state.domain.operational_spec = _spec(6)
        assert criteria_floor(state) == 6

    def test_a_clarified_thread_floors_at_the_criteria_it_names(self) -> None:
        state = _state()
        requirements = _eight_criterion_thread()
        state.domain.requirements = requirements
        floor = criteria_floor(state)
        assert floor >= 8
        # A floor over-counts a shared criterion; it may not read as a request
        # larger than the requirements themselves.
        assert floor <= len(requirements)
        limit = phase_usage_limits(floor).tool_calls_limit
        assert limit is not None
        assert limit >= 8 * CALLS_PER_CRITERION

    def test_a_combination_names_one_criterion_per_term(self) -> None:
        state = _state()
        state.domain.requirements = [
            _requirement(
                ConstraintKind.COMBINATION,
                "kinase identification",
                "domain OR ec number OR go term OR annotation",
            ),
        ]
        assert criteria_floor(state) == 4

    def test_a_restated_requirement_is_not_a_second_criterion(self) -> None:
        state = _state()
        state.domain.requirements = [
            _requirement(ConstraintKind.DATA_TYPE, "expression dataset", "trophozoite"),
            _requirement(ConstraintKind.DATA_TYPE, "expression dataset", "schizont"),
        ]
        assert criteria_floor(state) == 1

    def test_a_chatty_thread_cannot_spend_the_whole_turn(self) -> None:
        state = _state()
        state.domain.requirements = [
            _requirement(ConstraintKind.DATA_TYPE, f"dataset {i}", f"study {i}")
            for i in range(40)
        ]
        assert criteria_floor(state) == MAX_CRITERIA_FLOOR
        limit = phase_usage_limits(criteria_floor(state)).tool_calls_limit
        assert limit == MAX_PHASE_TOOL_CALLS


class TestTheCeilingFollowsTheDeclaredSize:
    def test_a_large_problem_gets_more_than_a_small_one(self) -> None:
        small = phase_usage_limits(2).tool_calls_limit
        large = phase_usage_limits(9).tool_calls_limit
        assert small is not None
        assert large is not None
        assert large > small

    def test_nine_criteria_fit(self) -> None:
        limit = phase_usage_limits(9).tool_calls_limit
        assert limit is not None
        assert limit >= 9 * CALLS_PER_CRITERION

    def test_a_vocabulary_heavy_shape_fits(self) -> None:
        # Ten criteria on a site whose parameters carry large vocabularies.
        limit = phase_usage_limits(10).tool_calls_limit
        assert limit is not None
        assert limit >= 100

    def test_the_structure_pass_is_paid_for_too(self) -> None:
        # Binding every criterion and then having nothing left to combine them
        # spends the whole budget for no strategy.
        limit = phase_usage_limits(4).tool_calls_limit
        assert limit is not None
        assert limit > 4 * CALLS_PER_CRITERION


class TestTheCeilingStaysInRange:
    @pytest.mark.parametrize("declared", [0, 1, 2])
    def test_a_small_problem_still_gets_room_to_recover(self, declared: int) -> None:
        limit = phase_usage_limits(declared).tool_calls_limit
        assert limit == MIN_PHASE_TOOL_CALLS

    def test_an_overstated_count_is_capped(self) -> None:
        assert phase_usage_limits(500).tool_calls_limit == MAX_PHASE_TOOL_CALLS

    def test_a_negative_count_is_not_a_negative_budget(self) -> None:
        assert phase_usage_limits(-3).tool_calls_limit == MIN_PHASE_TOOL_CALLS


class TestTheOtherCeilingsHold:
    def test_requests_match_calls(self) -> None:
        limits = phase_usage_limits(9)
        assert limits.request_limit == limits.tool_calls_limit

    def test_the_token_ceiling_is_not_what_binds(self) -> None:
        assert phase_usage_limits(9).total_tokens_limit == 2_000_000
