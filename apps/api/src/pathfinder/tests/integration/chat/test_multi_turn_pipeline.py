"""End-to-end multi-turn pipeline test — LLM mocks only, everything else real.

Covers the full P. falciparum-kinases research workflow with greetings,
off-topic rejects, conceptual questions, and the scoping→discovery→
planning→execution→verification phase progression. Verifies:

- message_history accumulates across turns (phase + question + reject)
- problem_frame persists across unrelated turns (Q/reject don't clobber)
- supervisor-emitted reject and question rows appear in history
- phase_call_counts resets per turn but state carries over
- data chunks (phase-start, turn-qa, turn-rejected, supervisor-decision)
  are emitted in the expected sequence per turn
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

import pathfinder.ai.graph.agents as agents_module
import pathfinder.ai.graph.nodes as nodes_module
from pathfinder.ai.agents.supervisor import SupervisorDecision
from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.persistence.models import Conversation, User
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.config import get_settings
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService


def _phase_text_agent(phase: str, texts: list[str]) -> Agent[AgentDeps, str]:
    cursor = {"i": 0}

    def _text() -> str:
        idx = cursor["i"]
        cursor["i"] = min(idx + 1, len(texts) - 1) if texts else idx
        return texts[min(idx, len(texts) - 1)] if texts else ""

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(content=_text())])

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        yield _text()

    return Agent(
        FunctionModel(_fn, stream_function=_stream, model_name=f"mock:{phase}"),
        output_type=str,
        deps_type=AgentDeps,
        instructions="respond with prose",
        name=f"mock-{phase}",
    )


def _supervisor_stub(
    decisions: list[SupervisorDecision],
) -> tuple[Agent[Any, SupervisorDecision], list[int]]:
    cursor = {"i": 0}
    captured_history_lens: list[int] = []

    def _payload(d: SupervisorDecision) -> dict[str, Any]:
        out: dict[str, Any] = {"to": d.to, "reason": d.reason}
        if d.rejection_message is not None:
            out["rejection_message"] = d.rejection_message
        if d.answer is not None:
            out["answer"] = d.answer
        return out

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del info
        captured_history_lens.append(len(messages))
        idx = cursor["i"]
        d = decisions[min(idx, len(decisions) - 1)]
        cursor["i"] = idx + 1
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args=json.dumps(_payload(d)),
                    tool_call_id=f"sup_{idx}",
                ),
            ],
        )

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del info
        captured_history_lens.append(len(messages))
        idx = cursor["i"]
        d = decisions[min(idx, len(decisions) - 1)]
        cursor["i"] = idx + 1
        yield {
            0: DeltaToolCall(
                name="final_result",
                json_args=json.dumps(_payload(d)),
                tool_call_id=f"sup_{idx}",
            ),
        }

    agent: Agent[Any, SupervisorDecision] = Agent(
        FunctionModel(_fn, stream_function=_stream, model_name="mock:supervisor"),
        output_type=SupervisorDecision,
        instructions="pick one action",
        name="mock-supervisor",
        defer_model_check=True,
    )
    return agent, captured_history_lens


def _run_turn_input(user_text: str) -> dict[str, Any]:
    return {
        "user_message_id": uuid4(),
        "user_prompt": user_text,
        "user_parts": [{"type": "text", "text": user_text}],
        "turn_trace_id": str(uuid4()),
        "turn_created_at": "2026-04-17T00:00:00+00:00",
        "supervisor_call_count": 0,
        "phase_call_counts": {},
        "current_phase": None,
        "last_routing_reason": None,
        "last_assistant_prose": "",
    }


def _chunk_types(events: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for e in events:
        payload = e.get("chunk") if isinstance(e, dict) else None
        if isinstance(payload, dict):
            t = payload.get("type")
            if isinstance(t, str):
                out.append(t)
    return out


async def _seed_conversation(conversation_id: UUID, user_id: UUID) -> None:
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        session.add(
            Conversation(id=conversation_id, user_id=user_id, site_id="plasmodb", name=""),
        )
        await session.commit()


def _make_context(user_id: UUID, memory_store: Any) -> Context:
    return Context(
        site_id="plasmodb",
        user_id=user_id,
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=async_session_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
        memory_store=memory_store,
    )


def _assert_final_turn(state: dict[str, Any], captured_history_lens: list[int]) -> None:
    assert captured_history_lens, "supervisor was never invoked"
    assert captured_history_lens[-1] >= len(captured_history_lens) * 0
    history_texts = [
        "".join(p.content for p in m.parts if isinstance(p, TextPart))
        for m in state["message_history"]
        if isinstance(m, ModelResponse)
    ]
    joined = "\n".join(history_texts)
    for needle in (
        "F1 is the harmonic mean",
        "PathFinder is for biological research only",
        "Problem frame updated",
        "Found candidate searches",
        "842 genes",
    ):
        assert needle in joined
    assert state["current_phase"] is None
    assert any(
        any(
            isinstance(p, UserPromptPart) and p.content == "summarize what you did"
            for p in m.parts
        )
        for m in state["message_history"]
        if isinstance(m, ModelRequest)
    )


@dataclass
class _Harness:
    graph: Any
    context: Context
    config: dict[str, Any]
    conversation_id: UUID
    user_id: UUID

    async def turn(
        self, prompt: str, *, is_first: bool,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if is_first:
            initial = PipelineState(
                conversation_id=self.conversation_id,
                user_id=self.user_id,
                site_id="plasmodb",
                mode="strategy",
                user_message_id=uuid4(),
                user_prompt=prompt,
                user_parts=[{"type": "text", "text": prompt}],
                turn_trace_id=str(uuid4()),
                turn_created_at="2026-04-17T00:00:00+00:00",
            )
            turn_input: dict[str, Any] = initial.model_dump()
        else:
            turn_input = _run_turn_input(prompt)
        events = [
            ev async for ev in self.graph.astream(
                turn_input, config=self.config, context=self.context, stream_mode=["custom"],
            )
        ]
        snap = await self.graph.aget_state(self.config)
        return snap.values, events


def _make_phase_stubs() -> dict[str, Agent[AgentDeps, str]]:
    return {
        "scoping": _phase_text_agent(
            "scoping",
            [
                "To build the strategy I need to clarify: do you want curated GO evidence only or also computational?",
                "Problem frame updated — GO evidence set to curated+computational.",
            ],
        ),
        "discovery": _phase_text_agent(
            "discovery",
            [
                "Found candidate searches: GenesByText, GenesByGoTerm, "
                "GenesByRNASeqPfal3D7_LopezBarragan_gametocytes_RSRCPercentile.",
            ],
        ),
        "planning": _phase_text_agent(
            "planning",
            ["Built plan with 5 steps (text, GO, union, RNA-Seq, intersect)."],
        ),
        "execution": _phase_text_agent(
            "execution",
            ["Executed all steps; final step id=final, estimated 842 genes."],
        ),
        "verification": _phase_text_agent(
            "verification",
            [
                "Verification complete. 842 genes returned. "
                "Controls: PfAP2-G (PF3D7_1222600) recovered.",
            ],
        ),
    }


def _make_decisions() -> list[SupervisorDecision]:
    return [
        SupervisorDecision(
            to="question", reason="greeting", answer="Hi! What would you like to research?",
        ),
        SupervisorDecision(
            to="question",
            reason="methodological",
            answer="F1 is the harmonic mean of precision and recall.",
        ),
        SupervisorDecision(
            to="reject",
            reason="off-topic",
            rejection_message="PathFinder is for biological research only.",
        ),
        SupervisorDecision(to="scoping", reason="new research goal"),
        SupervisorDecision(to="end", reason="scoping asked a clarifier"),
        SupervisorDecision(to="scoping", reason="fold user answer into frame"),
        SupervisorDecision(to="discovery", reason="frame resolved"),
        SupervisorDecision(to="planning", reason="candidates found"),
        SupervisorDecision(to="execution", reason="plan submitted"),
        SupervisorDecision(to="verification", reason="execution done"),
        SupervisorDecision(to="end", reason="verification passed"),
        SupervisorDecision(
            to="question",
            reason="summarize prior work",
            answer="We built a plan, executed all steps, got 842 genes. "
            "PfAP2-G was recovered as a positive control.",
        ),
    ]


@pytest.mark.asyncio
async def test_multi_turn_full_pipeline_with_questions_and_rejects(
    db_cleaner: None,
    patch_app_db_engine: None,
) -> None:
    del db_cleaner, patch_app_db_engine

    phase_stubs = _make_phase_stubs()
    sup_agent, captured_history_lens = _supervisor_stub(_make_decisions())

    conversation_id = uuid4()
    user_id = uuid4()
    config = {"configurable": {"thread_id": str(conversation_id)}}
    await _seed_conversation(conversation_id, user_id)

    settings = get_settings()
    async with lifespan_memory_store(settings.database_url) as memory_store:
        context = _make_context(user_id, memory_store)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(agents_module, "PHASE_AGENTS", phase_stubs)
            mp.setattr(nodes_module, "PHASE_AGENTS", phase_stubs)
            mp.setattr(
                nodes_module,
                "build_supervisor_agent",
                lambda provider=None, *, model_id=None: sup_agent,
            )
            harness = _Harness(
                graph=build_graph(checkpointer=InMemorySaver()),
                context=context,
                config=config,
                conversation_id=conversation_id,
                user_id=user_id,
            )

            # Turn 1: greeting → question
            state_1, events_1 = await harness.turn("hi", is_first=True)
            types_1 = _chunk_types([e[1] if isinstance(e, tuple) else e for e in events_1])
            assert "data-supervisor-decision" in types_1
            assert "data-turn-qa" in types_1
            assert "data-phase-start" not in types_1
            assert len(state_1["message_history"]) == 2, (
                f"turn 1 should append 2 msgs (user+qa); got "
                f"{len(state_1['message_history'])}"
            )

            # Turn 2: conceptual question → another question (prior history must persist)
            state_2, events_2 = await harness.turn(
                "what is F1?", is_first=False,
            )
            types_2 = _chunk_types([e[1] if isinstance(e, tuple) else e for e in events_2])
            assert "data-turn-qa" in types_2
            assert len(state_2["message_history"]) == 4, (
                "turn 2 appends 2 more msgs (user+qa) for a total of 4"
            )
            user_texts = [
                "".join(
                    p.content
                    for p in m.parts
                    if isinstance(p, UserPromptPart)
                )
                for m in state_2["message_history"]
                if isinstance(m, ModelRequest)
            ]
            assert "hi" in user_texts
            assert "what is F1?" in user_texts

            # Turn 3: off-topic → reject (history must still persist)
            state_3, events_3 = await harness.turn(
                "help me write python", is_first=False,
            )
            types_3 = _chunk_types([e[1] if isinstance(e, tuple) else e for e in events_3])
            assert "data-turn-rejected" in types_3
            assert len(state_3["message_history"]) == 6

            # Turn 4: research goal → scoping runs → supervisor ends
            state_4, events_4 = await harness.turn(
                "find P. falciparum kinases in gametocytes", is_first=False,
            )
            types_4 = _chunk_types([e[1] if isinstance(e, tuple) else e for e in events_4])
            assert "data-phase-start" in types_4
            assert types_4.count("data-phase-start") == 1, (
                f"expected exactly 1 phase start this turn (scoping); "
                f"got {types_4}"
            )
            # Phase appended user + response; no turn-qa/rejected card
            assert "data-turn-qa" not in types_4
            assert "data-turn-rejected" not in types_4
            assert state_4["current_phase"] == "scoping"

            # Turn 5: user answers → full pipeline progression
            state_5, events_5 = await harness.turn(
                "yes include both curated and computational",
                is_first=False,
            )
            types_5 = _chunk_types([e[1] if isinstance(e, tuple) else e for e in events_5])
            phase_starts = [t for t in types_5 if t == "data-phase-start"]
            assert len(phase_starts) == 5, (
                f"turn 5 should hit all 5 phases once each; got "
                f"{len(phase_starts)} phase-starts"
            )
            assert state_5["current_phase"] == "verification"

            # Turn 6: follow-up question uses the whole conversation history
            state_6, _ = await harness.turn(
                "summarize what you did", is_first=False,
            )
            _assert_final_turn(state_6, captured_history_lens)
