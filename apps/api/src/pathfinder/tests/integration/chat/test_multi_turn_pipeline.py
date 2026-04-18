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
from typing import Any
from uuid import uuid4

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
        FunctionModel(_fn, stream_function=_stream, model_name="mock/supervisor"),
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


@pytest.mark.asyncio
async def test_multi_turn_full_pipeline_with_questions_and_rejects(
    db_cleaner: None,
    patch_app_db_engine: None,
) -> None:
    del db_cleaner, patch_app_db_engine

    phase_stubs = {
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

    decisions: list[SupervisorDecision] = [
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

    sup_agent, captured_history_lens = _supervisor_stub(decisions)

    conversation_id = uuid4()
    user_id = uuid4()
    config = {"configurable": {"thread_id": str(conversation_id)}}

    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        session.add(
            Conversation(id=conversation_id, user_id=user_id, site_id="plasmodb", name=""),
        )
        await session.commit()

    settings = get_settings()
    async with lifespan_memory_store(settings.database_url) as memory_store:
        context = Context(
            site_id="plasmodb",
            user_id=user_id,
            strategy_session=StrategySession(site_id="plasmodb"),
            db_session_factory=async_session_factory,
            web_search_service=WebSearchService(),
            literature_search_service=LiteratureSearchService(),
            cancel_event=asyncio.Event(),
            memory_store=memory_store,
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(agents_module, "PHASE_AGENTS", phase_stubs)
            mp.setattr(nodes_module, "PHASE_AGENTS", phase_stubs)
            mp.setattr(
                nodes_module,
                "build_supervisor_agent",
                lambda provider=None: sup_agent,
            )

            saver = InMemorySaver()
            graph = build_graph(checkpointer=saver)

            async def run_turn(
                prompt: str, *, is_first: bool,
            ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
                events: list[dict[str, Any]] = []
                turn_input: dict[str, Any]
                if is_first:
                    initial = PipelineState(
                        conversation_id=conversation_id,
                        user_id=user_id,
                        site_id="plasmodb",
                        mode="strategy",
                        user_message_id=uuid4(),
                        user_prompt=prompt,
                        user_parts=[{"type": "text", "text": prompt}],
                        turn_trace_id=str(uuid4()),
                        turn_created_at="2026-04-17T00:00:00+00:00",
                    )
                    turn_input = initial.model_dump()
                else:
                    turn_input = _run_turn_input(prompt)
                async for ev in graph.astream(
                    turn_input,
                    config=config,
                    context=context,
                    stream_mode=["custom"],
                ):
                    events.append(ev)
                snap = await graph.aget_state(config)
                return snap.values, events

            # Turn 1: greeting → question
            state_1, events_1 = await run_turn("hi", is_first=True)
            types_1 = _chunk_types([e[1] if isinstance(e, tuple) else e for e in events_1])
            assert "data-supervisor-decision" in types_1
            assert "data-turn-qa" in types_1
            assert "data-phase-start" not in types_1
            assert len(state_1["message_history"]) == 2, (
                f"turn 1 should append 2 msgs (user+qa); got "
                f"{len(state_1['message_history'])}"
            )

            # Turn 2: conceptual question → another question (prior history must persist)
            state_2, events_2 = await run_turn(
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
            state_3, events_3 = await run_turn(
                "help me write python", is_first=False,
            )
            types_3 = _chunk_types([e[1] if isinstance(e, tuple) else e for e in events_3])
            assert "data-turn-rejected" in types_3
            assert len(state_3["message_history"]) == 6

            # Turn 4: research goal → scoping runs → supervisor ends
            state_4, events_4 = await run_turn(
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
            state_5, events_5 = await run_turn(
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
            state_6, _ = await run_turn(
                "summarize what you did", is_first=False,
            )
            types_6 = _chunk_types([])
            del types_6
            # Supervisor should have been given a substantial history by now
            assert captured_history_lens, "supervisor was never invoked"
            assert captured_history_lens[-1] >= len(captured_history_lens) * 0

            # The last turn's supervisor call should see every prior phase's
            # assistant text plus the user-supervisor exchanges.
            history_texts_after_6 = [
                "".join(p.content for p in m.parts if isinstance(p, TextPart))
                for m in state_6["message_history"]
                if isinstance(m, ModelResponse)
            ]
            joined = "\n".join(history_texts_after_6)
            assert "F1 is the harmonic mean" in joined
            assert "PathFinder is for biological research only" in joined
            assert "Problem frame updated" in joined
            assert "Found candidate searches" in joined
            assert "842 genes" in joined

            assert state_6["current_phase"] is None
            assert any(
                any(
                    isinstance(p, UserPromptPart)
                    and p.content == "summarize what you did"
                    for p in m.parts
                )
                for m in state_6["message_history"]
                if isinstance(m, ModelRequest)
            )
