"""The Lead sees the building tools only when this turn's intent asks to build.

A context statement and a memory request are answered in prose; the tools that
change a strategy are not on the model's list for those turns.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead.intent import IntentClassification
from pathfinder.ai.lead.intent_gate import BUILDING_TOOLS
from pathfinder.ai.lead.lead_agent import LeadResponse, build_lead_agent
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

_PROSE = "I can build that whenever you want. Want me to?"


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _deps(prompt: str) -> LeadDeps:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="tritrypdb",
        mode="strategy",
        user_prompt=prompt,
        domain=StrategyDomainState(),
    )
    return LeadDeps(
        state=state,
        intent=None,
        runtime=Context(
            site_id="tritrypdb",
            user_id=uuid4(),
            strategy_session=StrategySession(site_id="tritrypdb"),
            db_session_factory=_never_factory,
            web_search_service=WebSearchService(),
            literature_search_service=LiteratureSearchService(),
            cancel_event=asyncio.Event(),
        ),
        retrieved_memories=[],
    )


def _classify_args(prompt: str, classification: IntentClassification) -> dict[str, Any]:
    return {
        "intent": {
            "rawText": prompt,
            "classification": classification.value,
            "inferredGoal": "what the user is working on",
        },
    }


class _Seen:
    """The tool names the model was offered, one entry per model step."""

    def __init__(self) -> None:
        self.steps: list[frozenset[str]] = []


def _model(prompt: str, classification: IntentClassification | None, seen: _Seen):
    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages
        seen.steps.append(frozenset(t.name for t in info.function_tools))
        if classification is not None and len(seen.steps) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="classify_user_intent",
                        args=_classify_args(prompt, classification),
                        tool_call_id="call_classify",
                    ),
                ],
            )
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={"prose": _PROSE, "nextState": "await_user"},
                    tool_call_id="call_final",
                ),
            ],
        )

    return FunctionModel(_fn, model_name="scripted")


def _run(prompt: str, classification: IntentClassification | None) -> _Seen:
    seen = _Seen()
    agent = build_lead_agent()
    deps = _deps(prompt)
    result = asyncio.run(
        agent.run(prompt, deps=deps, model=_model(prompt, classification, seen)),
    )
    assert isinstance(result.output, LeadResponse)
    return seen


def test_an_unclassified_turn_is_offered_no_building_tool() -> None:
    seen = _run("I'm investigating virulence factors in Leishmania major", None)

    assert seen.steps
    assert not (seen.steps[0] & BUILDING_TOOLS)
    assert "classify_user_intent" in seen.steps[0]


def test_a_context_statement_is_offered_no_building_tool() -> None:
    seen = _run(
        "I'm investigating virulence factors in Leishmania major",
        IntentClassification.CONTEXT_STATEMENT,
    )

    assert len(seen.steps) == 2
    assert not (seen.steps[1] & BUILDING_TOOLS)
    assert {"get_live_strategy_state", "read_ledger_section", "remember"} <= (
        seen.steps[1]
    )


def test_a_memory_request_keeps_remember_and_hides_the_building_tools() -> None:
    seen = _run(
        "Please remember for future sessions that I work on P. falciparum 3D7.",
        IntentClassification.MEMORY_REQUEST,
    )

    assert "remember" in seen.steps[1]
    assert "frame_problem" not in seen.steps[1]
    assert "build_strategy" not in seen.steps[1]
    assert "run_eda_compute" not in seen.steps[1]


@pytest.mark.parametrize(
    "classification",
    [
        IntentClassification.NEW_STRATEGY,
        IntentClassification.EXTEND_STRATEGY,
        IntentClassification.EDIT_STRATEGY,
        IntentClassification.CLARIFICATION_RESPONSE,
        IntentClassification.SLOT_ANSWER,
        IntentClassification.APPROVAL,
    ],
)
def test_an_intent_that_builds_is_offered_every_building_tool(
    classification: IntentClassification,
) -> None:
    seen = _run("Find A. gambiae midgut proteases", classification)

    assert seen.steps[1] >= BUILDING_TOOLS


@pytest.mark.parametrize(
    "classification",
    [
        IntentClassification.FOLLOW_UP_QUESTION,
        IntentClassification.OFF_TOPIC,
        IntentClassification.DENIAL,
    ],
)
def test_an_intent_that_does_not_build_is_offered_none_of_them(
    classification: IntentClassification,
) -> None:
    seen = _run("What does that step do?", classification)

    assert not (seen.steps[1] & BUILDING_TOOLS)


def test_a_context_statement_turn_answers_in_prose() -> None:
    seen = _Seen()
    agent = build_lead_agent()
    prompt = "I'm investigating virulence factors in Leishmania major"
    result = asyncio.run(
        agent.run(
            prompt,
            deps=_deps(prompt),
            model=_model(prompt, IntentClassification.CONTEXT_STATEMENT, seen),
        ),
    )

    assert isinstance(result.output, LeadResponse)
    assert result.output.prose == _PROSE


def _reclassifying_model(prompt: str, seen: _Seen) -> FunctionModel:
    """A turn that classifies a build as a question, then corrects itself."""

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages
        seen.steps.append(frozenset(t.name for t in info.function_tools))
        step = len(seen.steps)
        if step == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="classify_user_intent",
                        args=_classify_args(
                            prompt,
                            IntentClassification.FOLLOW_UP_QUESTION,
                        ),
                        tool_call_id="call_first",
                    ),
                ],
            )
        if step == 2:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="classify_user_intent",
                        args=_classify_args(
                            prompt,
                            IntentClassification.EXTEND_STRATEGY,
                        ),
                        tool_call_id="call_second",
                    ),
                ],
            )
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={"prose": _PROSE, "nextState": "await_user"},
                    tool_call_id="call_final",
                ),
            ],
        )

    return FunctionModel(_fn, model_name="scripted")


def test_a_corrected_classification_unhides_the_building_tools() -> None:
    """A misclassified build degrades to one wasted step, not to a refusal."""
    prompt = (
        "Yes, rerun the differential expression and then create the strategy "
        "step from the genes that pass."
    )
    seen = _Seen()
    agent = build_lead_agent()
    result = asyncio.run(
        agent.run(
            prompt,
            deps=_deps(prompt),
            model=_reclassifying_model(prompt, seen),
        ),
    )

    assert isinstance(result.output, LeadResponse)
    assert len(seen.steps) == 3
    assert not (seen.steps[1] & BUILDING_TOOLS)
    assert seen.steps[2] >= BUILDING_TOOLS
    assert {"build_strategy", "edit_strategy"} <= seen.steps[2]
