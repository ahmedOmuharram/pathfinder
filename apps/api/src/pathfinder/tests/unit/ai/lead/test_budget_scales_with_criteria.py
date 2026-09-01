"""The phase ceiling follows the size of the problem the Lead declares.

A constant is generous for a two-criterion request and impossible for a
nine-criterion one. The Lead reads the goal before dispatching FRAME, so it is
the only place that knows the size in advance.
"""

from __future__ import annotations

import pytest

from pathfinder.ai.lead.sub_agent_tools import (
    CALLS_PER_CRITERION,
    MAX_PHASE_TOOL_CALLS,
    MIN_PHASE_TOOL_CALLS,
    phase_usage_limits,
)


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
