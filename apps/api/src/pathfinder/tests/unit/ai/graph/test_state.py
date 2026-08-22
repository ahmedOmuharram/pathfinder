from __future__ import annotations

from typing import get_args
from uuid import uuid4

import pytest
from pydantic import ValidationError

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.state import (
    PHASE_NAMES,
    PhaseDisposition,
    PhaseName,
    PipelineState,
    StrategyDomainState,
    VerificationDigest,
)
from pathfinder.domain.strategy.operational_spec import Criterion, OperationalSpec


@pytest.fixture
def base_state() -> PipelineState:
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
    )


def test_phase_names_constant_matches_literal_args() -> None:
    assert set(PHASE_NAMES) == set(get_args(PhaseName))
    assert PHASE_NAMES == (
        "frame",
        "build",
        "verification",
    )


def test_state_minimum_construction(base_state: PipelineState) -> None:
    assert base_state.site_id == "plasmodb"
    assert base_state.mode == "strategy"
    assert base_state.user_prompt == ""
    assert base_state.user_parts == []
    assert base_state.domain.discovered_searches == {}
    assert base_state.domain.operational_spec is None
    assert base_state.domain.verification_digest is None
    assert base_state.domain.last_build_outcome is None
    assert base_state.domain.user_intent is None
    # Cross-phase / cross-turn context now flows through typed fields, not
    # a raw model trace — drop the field so checkpoints stay small.
    assert not hasattr(base_state, "message_history")
    assert not hasattr(base_state, "current_phase")
    assert not hasattr(base_state, "supervisor_log")
    assert not hasattr(base_state, "specialist_mode")


def test_state_carries_verification_digest(
    base_state: PipelineState,
) -> None:
    """Verification digest is the only typed exit signal under the Lead
    architecture; round-trip through JSON proves it survives the
    LangGraph checkpoint shape."""
    digest = VerificationDigest(
        disposition=PhaseDisposition.DONE,
        prose="Strategy ready.",
        reason="verification successful",
        success=True,
        key_findings=["1234 hits"],
    )
    state = base_state.model_copy(
        update={"domain": StrategyDomainState(verification_digest=digest)},
    )
    rehydrated = PipelineState.model_validate(state.model_dump(mode="json"))
    digest_back = rehydrated.domain.verification_digest
    assert digest_back is not None
    assert digest_back.disposition == PhaseDisposition.DONE
    assert digest_back.success is True
    assert digest_back.key_findings == ["1234 hits"]


def test_state_carries_operational_spec(base_state: PipelineState) -> None:
    spec = OperationalSpec(
        goal="find drug targets",
        interpreted_goal="find drug targets in P. falciparum",
        organism_scope="P. falciparum",
        criteria=[
            Criterion(id="c1", text="kinases", search_name="GenesByGoTerm"),
        ],
    )
    state = base_state.model_copy(
        update={"domain": StrategyDomainState(operational_spec=spec)},
    )
    rehydrated = PipelineState.model_validate(state.model_dump(mode="json"))
    spec_back = rehydrated.domain.operational_spec
    assert spec_back is not None
    assert spec_back.goal == "find drug targets"
    assert spec_back.criteria[0].search_name == "GenesByGoTerm"


def test_state_carries_discovered_searches(base_state: PipelineState) -> None:
    overview = SearchOverview(
        search_name="GenesByExpression",
        display_name="Genes by Expression",
        record_type="transcript",
        description="",
        parameter_names=["dataset"],
        required_params=["dataset"],
    )
    state = base_state.model_copy(
        update={
            "domain": StrategyDomainState(
                discovered_searches={"GenesByExpression": overview},
            ),
        },
    )
    rehydrated = PipelineState.model_validate(state.model_dump(mode="json"))
    searches = rehydrated.domain.discovered_searches
    assert "GenesByExpression" in searches
    assert searches["GenesByExpression"].display_name == "Genes by Expression"


def test_state_rejects_negative_total_tokens() -> None:
    """Sanity: PipelineState validation works on at least one field."""
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        turn_total_tokens=42,
    )
    assert state.turn_total_tokens == 42
    with pytest.raises(ValidationError):
        PipelineState.model_validate(
            {
                "conversation_id": str(uuid4()),
                "user_id": str(uuid4()),
                "site_id": "plasmodb",
                "mode": "strategy",
                "turn_total_tokens": "not a number",
            },
        )


class TestCheckpointsFromBeforeTheFbvFlip:
    """A checkpoint written by the five-phase pipeline must be REJECTED.

    ``PipelineState`` used to leave Pydantic's ``extra`` at its default, so a
    stale key was silently dropped. That is a compatibility shim for a shape
    that no longer exists, and it hides drift exactly the way an ``as Step``
    cast did: a field renamed in code goes quiet instead of loud.

    The state is strict now, and the old-shape checkpoints are truncated by
    the migration that accompanies it. PathFinder has not shipped, so there
    is nothing to stay compatible with.
    """

    def _old_shape(self) -> dict[str, object]:
        return {
            "conversation_id": str(uuid4()),
            "user_id": str(uuid4()),
            "site_id": "plasmodb",
            "mode": "strategy",
            "user_prompt": "gametocyte upregulated genes",
            # Fields the five-phase pipeline wrote and FRAME/BUILD/VERIFY removed.
            "active_plan": {"steps": [{"searchName": "GenesByTaxon"}]},
        }

    def test_a_pre_flip_checkpoint_is_rejected_loudly(self) -> None:
        with pytest.raises(ValidationError, match="active_plan"):
            PipelineState.model_validate(self._old_shape())

    def test_a_typo_in_a_field_name_is_rejected(self) -> None:
        # The real payoff: renaming a field can no longer half-land, with
        # writers setting a key readers silently ignore.
        payload = {
            "conversation_id": str(uuid4()),
            "user_id": str(uuid4()),
            "site_id": "plasmodb",
            "mode": "strategy",
            "operationl_spec": None,
        }

        with pytest.raises(ValidationError, match="operationl_spec"):
            PipelineState.model_validate(payload)

    def test_the_current_shape_still_validates(self) -> None:
        state = PipelineState.model_validate(
            {
                "conversation_id": str(uuid4()),
                "user_id": str(uuid4()),
                "site_id": "plasmodb",
                "mode": "strategy",
                "user_prompt": "gametocyte upregulated genes",
            }
        )

        assert state.domain.operational_spec is None
