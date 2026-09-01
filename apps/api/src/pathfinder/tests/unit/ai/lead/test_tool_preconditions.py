"""Each phase tool is on the Lead's list only when its precondition holds.

The classification is the turn's own, so a building intent from an earlier
message unlocks nothing. Every other precondition is read from the ledger, the
live graph and what this turn already did.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.ai.lead.intent_gate import BUILDING_TOOLS, UNCLASSIFIED_TOOLS
from pathfinder.ai.lead.lead_agent import LeadResponse, build_lead_agent
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.graph_model import flatten_tree
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OperationalSpec,
)
from pathfinder.domain.strategy.session import (
    StrategyGraph,
    StrategySession,
)
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

_PROSE = "Here is what I found."
_PROMPT = "Find A. gambiae midgut proteases"


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _session(*, with_steps: bool) -> StrategySession:
    session = StrategySession(site_id="plasmodb")
    if not with_steps:
        return session
    graph = StrategyGraph(graph_id="g1", name="Kinases", site_id="plasmodb")
    graph.record_type = "transcript"
    graph.steps = flatten_tree(
        StrategyStepNode(id="step_a", search_name="GenesByText"),
    )
    graph.recompute_roots()
    session.graph = graph
    return session


def _intent(classification: IntentClassification) -> UserIntent:
    return UserIntent(
        raw_text=_PROMPT,
        classification=classification,
        inferred_goal="what the user asked for",
    )


def _deps(
    *,
    classification: IntentClassification | None = None,
    classified_this_turn: bool = True,
    domain: StrategyDomainState | None = None,
    with_steps: bool = False,
) -> LeadDeps:
    message_id = uuid4()
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt=_PROMPT,
        user_message_id=message_id,
        domain=domain if domain is not None else StrategyDomainState(),
    )
    intent = None if classification is None else _intent(classification)
    if intent is not None and classified_this_turn:
        state.turn_markers.intent_classified = True
    return LeadDeps(
        state=state,
        intent=intent,
        runtime=Context(
            site_id="plasmodb",
            user_id=state.user_id,
            strategy_session=_session(with_steps=with_steps),
            db_session_factory=_never_factory,
            web_search_service=WebSearchService(),
            literature_search_service=LiteratureSearchService(),
            cancel_event=asyncio.Event(),
        ),
        retrieved_memories=[],
    )


class _Seen:
    """The tool names the model was offered, one entry per model step."""

    def __init__(self) -> None:
        self.steps: list[frozenset[str]] = []


def _final_only(seen: _Seen) -> FunctionModel:
    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages
        seen.steps.append(frozenset(t.name for t in info.function_tools))
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


def _offered(deps: LeadDeps) -> frozenset[str]:
    seen = _Seen()
    result = asyncio.run(
        build_lead_agent().run(_PROMPT, deps=deps, model=_final_only(seen)),
    )
    assert isinstance(result.output, LeadResponse)
    return seen.steps[0]


def _spec_with_criteria() -> OperationalSpec:
    return OperationalSpec(
        goal="kinases",
        criteria=[Criterion(id="c1", text="kinases", search_name="GenesByText")],
    )


def _zero_build() -> BuildOutcome:
    return BuildOutcome(pushed_step_ids=["step_a"], zero_step_ids=["step_a"])


def test_a_prior_turns_intent_does_not_unlock_this_turn() -> None:
    """A building classification carried over from an earlier message is stale."""
    offered = _offered(
        _deps(
            classification=IntentClassification.NEW_STRATEGY,
            classified_this_turn=False,
        ),
    )

    assert not (offered & BUILDING_TOOLS)
    assert "classify_user_intent" in offered


def test_an_unclassified_turn_reaches_only_the_always_on_tools() -> None:
    offered = _offered(_deps())

    assert offered == UNCLASSIFIED_TOOLS


def test_a_classified_build_turn_reaches_frame_and_build() -> None:
    offered = _offered(_deps(classification=IntentClassification.NEW_STRATEGY))

    assert {"frame_problem", "build_strategy"} <= offered


def test_frame_is_hidden_once_a_frame_dispatch_ran_this_turn() -> None:
    deps = _deps(classification=IntentClassification.NEW_STRATEGY)
    deps.state.turn_markers.framed = True

    assert "frame_problem" not in _offered(deps)


def test_frame_is_hidden_for_an_edit_intent_over_existing_criteria() -> None:
    deps = _deps(
        classification=IntentClassification.EDIT_STRATEGY,
        domain=StrategyDomainState(operational_spec=_spec_with_criteria()),
        with_steps=True,
    )

    offered = _offered(deps)

    assert "frame_problem" not in offered
    assert "edit_strategy" in offered


def test_frame_is_offered_for_an_edit_intent_with_no_criteria_yet() -> None:
    deps = _deps(classification=IntentClassification.EDIT_STRATEGY)

    assert "frame_problem" in _offered(deps)


def test_frame_is_offered_when_an_edit_has_no_strategy_to_edit() -> None:
    """``edit_strategy`` refuses without steps and names ``frame_problem``."""
    deps = _deps(
        classification=IntentClassification.EDIT_STRATEGY,
        domain=StrategyDomainState(operational_spec=_spec_with_criteria()),
    )

    assert "frame_problem" in _offered(deps)


def test_frame_is_hidden_after_a_build_this_turn_returned_nothing() -> None:
    deps = _deps(
        classification=IntentClassification.NEW_STRATEGY,
        domain=StrategyDomainState(last_build_outcome=_zero_build()),
        with_steps=True,
    )
    deps.state.turn_markers.built = True

    assert "frame_problem" not in _offered(deps)


def test_a_new_message_reopens_frame_after_an_empty_build() -> None:
    """The zero result is answered by the user, and their answer re-frames."""
    deps = _deps(
        classification=IntentClassification.NEW_STRATEGY,
        domain=StrategyDomainState(last_build_outcome=_zero_build()),
    )

    assert "frame_problem" in _offered(deps)


def test_build_is_hidden_when_the_strategy_already_has_steps() -> None:
    deps = _deps(
        classification=IntentClassification.EXTEND_STRATEGY,
        with_steps=True,
    )

    assert "build_strategy" not in _offered(deps)


def test_verify_is_hidden_until_something_is_built() -> None:
    deps = _deps(classification=IntentClassification.NEW_STRATEGY)

    assert "verify_strategy" not in _offered(deps)


def test_verify_is_offered_once_a_build_recorded_an_outcome() -> None:
    deps = _deps(
        classification=IntentClassification.NEW_STRATEGY,
        domain=StrategyDomainState(last_build_outcome=BuildOutcome()),
    )

    assert "verify_strategy" in _offered(deps)


def test_verify_is_offered_for_a_step_exported_without_a_build() -> None:
    """An EDA export leaves a real step and no build outcome."""
    deps = _deps(
        classification=IntentClassification.EXTEND_STRATEGY,
        with_steps=True,
    )

    assert "verify_strategy" in _offered(deps)


def test_verify_is_hidden_once_it_succeeded_this_turn() -> None:
    deps = _deps(
        classification=IntentClassification.NEW_STRATEGY,
        domain=StrategyDomainState(last_build_outcome=BuildOutcome()),
    )
    deps.state.turn_markers.verified = True

    assert "verify_strategy" not in _offered(deps)


def test_create_eda_step_is_hidden_until_a_preview_counted_the_subset() -> None:
    deps = _deps(classification=IntentClassification.EXTEND_STRATEGY)

    assert "create_eda_step" not in _offered(deps)


def test_create_eda_step_is_offered_after_a_preview_this_turn() -> None:
    deps = _deps(classification=IntentClassification.EXTEND_STRATEGY)
    deps.state.turn_markers.eda_previewed = True

    assert "create_eda_step" in _offered(deps)


def test_the_markers_belong_to_the_message_they_were_written_for() -> None:
    """The record rotates when the turn answers a different user message."""
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_message_id=UUID(int=1),
    )
    state.turn_markers.intent_classified = True
    state.turn_markers.framed = True

    state.user_message_id = UUID(int=2)

    assert not state.turn_markers.intent_classified
    assert not state.turn_markers.framed
    assert state.turn_markers.message_id == UUID(int=2)


def _classify_args(classification: IntentClassification) -> dict[str, Any]:
    return {
        "intent": {
            "rawText": _PROMPT,
            "classification": classification.value,
            "inferredGoal": "what the user asked for",
        },
    }


def test_classifying_this_turn_marks_the_turn_and_unlocks_the_tools() -> None:
    """The degrade path: one classification, and the tools are back."""
    seen = _Seen()

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages
        seen.steps.append(frozenset(t.name for t in info.function_tools))
        if len(seen.steps) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="classify_user_intent",
                        args=_classify_args(IntentClassification.NEW_STRATEGY),
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

    deps = _deps(
        classification=IntentClassification.FOLLOW_UP_QUESTION,
        classified_this_turn=False,
    )
    result = asyncio.run(
        build_lead_agent().run(
            _PROMPT,
            deps=deps,
            model=FunctionModel(_fn, model_name="scripted"),
        ),
    )

    assert isinstance(result.output, LeadResponse)
    assert seen.steps[0] == UNCLASSIFIED_TOOLS
    assert {"frame_problem", "build_strategy"} <= seen.steps[1]
    assert deps.state.turn_markers.intent_classified
