"""A turn that built something cannot answer without verifying it.

The precondition gate offers ``verify_strategy``; it cannot compel the call.
The output validator does, once per turn: the second answer goes through even
when it still declines, because only the model knows whether a check is
possible right now.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.tools import DeferredToolRequests
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.ai.lead.lead_agent import LeadResponse, build_lead_agent
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

_PROMPT = "Export the heat-shock genes as a step"
_PROSE = "I added the step."


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _deps(
    *,
    built: bool,
    verified: bool = False,
    dispatched: bool = False,
) -> LeadDeps:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt=_PROMPT,
        user_message_id=uuid4(),
    )
    state.turn_markers.intent_classified = True
    if built:
        state.record_build(BuildOutcome(pushed_step_ids=["step_1"], root_count=1543))
    state.turn_markers.verified = verified
    state.turn_markers.verification_dispatched = dispatched
    return LeadDeps(
        state=state,
        intent=UserIntent(
            raw_text=_PROMPT,
            classification=IntentClassification.EXTEND_STRATEGY,
            inferred_goal="export the subset",
        ),
        runtime=Context(
            site_id="plasmodb",
            user_id=state.user_id,
            strategy_session=StrategySession(site_id="plasmodb"),
            db_session_factory=_never_factory,
            web_search_service=WebSearchService(),
            literature_search_service=LiteratureSearchService(),
            cancel_event=asyncio.Event(),
        ),
        retrieved_memories=[],
    )


class _Parks:
    """A script that parks the turn on an approval instead of answering."""

    def __init__(self) -> None:
        self.retries: list[str] = []

    def model(self) -> FunctionModel:
        def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            del info
            request = messages[-1]
            if isinstance(request, ModelRequest):
                self.retries.extend(
                    part.model_response()
                    for part in request.parts
                    if isinstance(part, RetryPromptPart)
                )
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="consult_user",
                        args={
                            "questions": [
                                {"id": "q1", "prompt": "Which arm should I add?"}
                            ],
                        },
                        tool_call_id="call_consult",
                    ),
                ],
            )

        return FunctionModel(_fn, model_name="scripted")


class _Answers:
    """A script that answers with prose and records what it was told."""

    def __init__(self) -> None:
        self.retries: list[str] = []

    def model(self) -> FunctionModel:
        def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            del info
            request = messages[-1]
            if isinstance(request, ModelRequest):
                self.retries.extend(
                    part.model_response()
                    for part in request.parts
                    if isinstance(part, RetryPromptPart)
                )
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={"prose": _PROSE, "nextState": "await_user"},
                        tool_call_id=f"call_{len(self.retries)}",
                    ),
                ],
            )

        return FunctionModel(_fn, model_name="scripted")


def _run(deps: LeadDeps) -> _Answers:
    script = _Answers()
    result = asyncio.run(
        build_lead_agent().run(_PROMPT, deps=deps, model=script.model()),
    )
    assert isinstance(result.output, LeadResponse)
    assert result.output.prose == _PROSE
    return script


def test_a_built_turn_that_never_verified_is_asked_once() -> None:
    deps = _deps(built=True)

    script = _run(deps)

    assert len(script.retries) == 1
    assert "verify_strategy" in script.retries[0]
    assert "1 step(s) on VEuPathDB" in script.retries[0]
    assert "root count 1543" in script.retries[0]
    assert deps.state.turn_markers.verification_nudged is True


def test_the_second_answer_goes_through_even_when_it_still_declines() -> None:
    """The nudge compels the attempt, not the outcome."""
    deps = _deps(built=True)

    script = _run(deps)

    assert len(script.retries) == 1


def test_a_verified_turn_is_never_asked() -> None:
    deps = _deps(built=True, verified=True)

    assert _run(deps).retries == []
    assert deps.state.turn_markers.verification_nudged is False


def test_a_verification_that_ran_and_failed_is_never_asked_again() -> None:
    """A dispatch that reported failure already checked the build."""
    deps = _deps(built=True, dispatched=True)

    assert _run(deps).retries == []


def test_a_turn_that_built_nothing_is_never_asked() -> None:
    deps = _deps(built=False)

    assert _run(deps).retries == []


def test_a_turn_that_parks_on_an_approval_is_never_asked() -> None:
    """A parked turn has not answered yet, so there is nothing to refuse."""
    deps = _deps(built=True)
    script = _Parks()

    result = asyncio.run(
        build_lead_agent().run(_PROMPT, deps=deps, model=script.model()),
    )

    assert isinstance(result.output, DeferredToolRequests)
    assert script.retries == []
    assert deps.state.turn_markers.verification_nudged is False
