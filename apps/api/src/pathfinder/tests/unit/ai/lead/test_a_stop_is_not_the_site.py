"""The reply may not attribute an internal stop to VEuPathDB.

A dispatch that ran out of calls is the turn's own limit. A reply that asks the
user to wait for the site while no VEuPathDB call of the turn failed is refused
and rewritten.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from pydantic_ai import DeferredToolRequests, RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RunUsage
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.lead_agent import LeadResponse, refuse_blaming_the_site
from pathfinder.ai.lead.ledger import blamed_the_site
from pathfinder.ai.lead.ledger_sections import BuildSection
from pathfinder.ai.lead.phase_stop import PhaseStop, PhaseStopReason
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.strategy.build_outcome import BuildOutcome, StepPushFailure
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

_BLAMING_REPLY = (
    "I kept every requirement you stated. Please try the build again once the "
    "site finishes refreshing the plan's search bindings; I will then "
    "materialize and verify it without changing these requirements."
)
_REAL_FAILURE_REPLY = (
    "VEuPathDB refused one step with a 422 on the organism parameter, so the "
    "build pushed two steps of three. Try again later once I re-bind that "
    "criterion."
)
_CLEAN_REPLY = (
    "The planning pass stopped on its call budget with three of eight criteria "
    "bound. I am running it again on the remaining five."
)


class TestTheMatcher:
    def test_a_wait_for_the_site_over_a_clean_build_is_blame(self) -> None:
        assert blamed_the_site(_BLAMING_REPLY, build=BuildSection()) is not None

    def test_a_reply_that_names_a_real_failure_is_not_refused(self) -> None:
        build = BuildSection(
            outcome=BuildOutcome(
                pushed_step_ids=["s1", "s2"],
                failed_steps=[
                    StepPushFailure(
                        step_id="s3", search_name="GenesByTaxon", error="422"
                    ),
                ],
            ),
            pushed_count=2,
            failed_count=1,
        )
        assert blamed_the_site(_REAL_FAILURE_REPLY, build=build) is None

    def test_an_empty_step_is_a_real_failure(self) -> None:
        build = BuildSection(
            outcome=BuildOutcome(pushed_step_ids=["s1"]),
            pushed_count=1,
            zero_result_steps=["s1"],
        )
        assert blamed_the_site(_BLAMING_REPLY, build=build) is None

    def test_a_reply_that_blames_nothing_passes(self) -> None:
        assert blamed_the_site(_CLEAN_REPLY, build=BuildSection()) is None

    def test_naming_the_site_without_blame_passes(self) -> None:
        text = "The strategy holds 132 genes and is saved on VEuPathDB."
        assert blamed_the_site(text, build=BuildSection()) is None


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _deps() -> LeadDeps:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="Now build.",
    )
    context = Context(
        site_id="plasmodb",
        user_id=uuid4(),
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    return LeadDeps(
        state=state,
        intent=None,
        runtime=context,
        retrieved_memories=[],
    )


def _model() -> FunctionModel:
    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(content="")])

    return FunctionModel(_fn, model_name="scripted")


def _ctx(deps: LeadDeps) -> RunContext[LeadDeps]:
    return RunContext(deps=deps, model=_model(), usage=RunUsage())


def test_the_blaming_reply_is_refused_and_told_the_real_stop() -> None:
    deps = _deps()
    deps.last_phase_stop = PhaseStop(
        role="frame",
        reason=PhaseStopReason.BUDGET,
        tool_calls=60,
        criteria_bound=3,
        criteria_declared=8,
    )

    with pytest.raises(ModelRetry) as raised:
        refuse_blaming_the_site(_ctx(deps), LeadResponse(prose=_BLAMING_REPLY))

    assert "the framing pass stopped on its call budget after 60 calls" in str(
        raised.value
    )


def test_the_refusal_is_asked_once_per_turn() -> None:
    deps = _deps()
    output = LeadResponse(prose=_BLAMING_REPLY)

    with pytest.raises(ModelRetry):
        refuse_blaming_the_site(_ctx(deps), output)

    assert refuse_blaming_the_site(_ctx(deps), output) is output


def test_a_reply_naming_a_real_wdk_failure_stands() -> None:
    deps = _deps()
    deps.state.domain.last_build_outcome = BuildOutcome(
        pushed_step_ids=["s1", "s2"],
        failed_steps=[
            StepPushFailure(step_id="s3", search_name="GenesByTaxon", error="422"),
        ],
    )
    output = LeadResponse(prose=_REAL_FAILURE_REPLY)

    assert refuse_blaming_the_site(_ctx(deps), output) is output


def test_a_reply_that_blames_nothing_stands() -> None:
    deps = _deps()
    output = LeadResponse(prose=_CLEAN_REPLY)

    assert refuse_blaming_the_site(_ctx(deps), output) is output


def test_a_deferred_request_is_not_prose() -> None:
    deps = _deps()
    output = DeferredToolRequests()

    assert refuse_blaming_the_site(_ctx(deps), output) is output
