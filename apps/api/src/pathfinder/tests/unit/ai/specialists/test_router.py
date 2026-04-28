from datetime import UTC, datetime
from uuid import uuid4

from pathfinder.ai.graph.builder import specialist_router
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.specialists.types import (
    ResearchContext,
    SpecialistMode,
    ValidateContext,
)


def _state(**overrides: object) -> PipelineState:
    base = {
        "conversation_id": uuid4(),
        "user_id": uuid4(),
        "site_id": "plasmodb",
        "mode": "chat",
    }
    base.update(overrides)
    return PipelineState.model_validate(base)


def test_router_returns_supervisor_when_no_specialist_mode() -> None:
    assert specialist_router(_state()) == "supervisor"


def test_router_returns_validate_when_specialist_mode_is_validate() -> None:
    state = _state(
        specialist_mode=SpecialistMode(
            kind="validate",
            entered_at=datetime.now(UTC),
            model_id="anthropic:claude-sonnet-4-5",
            context=ValidateContext(strategy_name="demo"),
        ),
    )
    assert specialist_router(state) == "validate"


def test_router_returns_research_when_specialist_mode_is_research() -> None:
    state = _state(
        specialist_mode=SpecialistMode(
            kind="research",
            entered_at=datetime.now(UTC),
            model_id="anthropic:claude-haiku-4-5",
            context=ResearchContext(research_question="what is PfEMP1?"),
        ),
    )
    assert specialist_router(state) == "research"


def test_validate_specialist_mode_round_trips_through_pipeline_state() -> None:
    mode = SpecialistMode(
        kind="validate",
        entered_at=datetime.now(UTC),
        model_id="anthropic:claude-sonnet-4-5",
        context=ValidateContext(strategy_name="demo"),
    )
    dumped = _state(specialist_mode=mode).model_dump(mode="json", by_alias=True)
    restored = PipelineState.model_validate(dumped)
    assert restored.specialist_mode is not None
    assert restored.specialist_mode.kind == "validate"
    assert restored.specialist_mode.context.kind == "validate"


def test_research_specialist_mode_round_trips_through_pipeline_state() -> None:
    mode = SpecialistMode(
        kind="research",
        entered_at=datetime.now(UTC),
        model_id="anthropic:claude-haiku-4-5",
        context=ResearchContext(research_question="what is PfEMP1?"),
    )
    dumped = _state(specialist_mode=mode).model_dump(mode="json", by_alias=True)
    restored = PipelineState.model_validate(dumped)
    assert restored.specialist_mode is not None
    assert restored.specialist_mode.kind == "research"
    assert restored.specialist_mode.context.kind == "research"
