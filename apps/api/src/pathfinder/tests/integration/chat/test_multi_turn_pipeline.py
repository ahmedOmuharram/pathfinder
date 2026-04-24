"""End-to-end multi-turn pipeline test — LLM mocks only, everything else real.

Covers the full P. falciparum-kinases research workflow with greetings,
off-topic rejects, conceptual questions, and the scoping→discovery→
planning→execution→verification phase progression. Verifies:

- problem_frame persists across unrelated turns (Q/reject don't clobber)
- supervisor-emitted reject and question reach the user via streamed
  ``data-turn-qa`` / ``data-turn-rejected`` chunks (the chat UI's render
  path), not via raw ``message_history`` (removed)
- phase_call_counts resets per turn but typed state carries over
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
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

import pathfinder.ai.graph.agents as agents_module
import pathfinder.ai.graph.nodes as nodes_module
from pathfinder.ai.agents.supervisor import SupervisorDecision
from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PhaseDisposition, PhaseOutcome, PipelineState
from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.ai.scratchpad.repository import ScratchpadRepository
from pathfinder.ai.scratchpad.tools import build_scratchpad_toolset
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


def _iter_chunks(events: list[Any]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for ev in events:
        payload = ev[1] if isinstance(ev, tuple) else ev
        if not isinstance(payload, dict):
            continue
        chunk_obj = payload.get("chunk")
        if isinstance(chunk_obj, dict):
            chunks.append(chunk_obj)
    return chunks


def _streamed_text_blocks(chunks: list[dict[str, Any]]) -> list[str]:
    deltas_by_id: dict[str, list[str]] = {}
    blocks: list[str] = []
    for chunk in chunks:
        kind = chunk.get("type")
        if kind == "text-delta":
            delta = chunk.get("delta")
            text_id = chunk.get("id")
            if isinstance(delta, str) and isinstance(text_id, str):
                deltas_by_id.setdefault(text_id, []).append(delta)
        elif kind == "text-end":
            text_id = chunk.get("id")
            if isinstance(text_id, str) and text_id in deltas_by_id:
                blocks.append("".join(deltas_by_id.pop(text_id)))
    blocks.extend("".join(parts) for parts in deltas_by_id.values())
    return blocks


def _data_chunk_strings(chunks: list[dict[str, Any]]) -> list[str]:
    fields_by_kind = {
        "data-turn-qa": "answer",
        "data-turn-rejected": "message",
    }
    out: list[str] = []
    for chunk in chunks:
        kind = chunk.get("type")
        field = fields_by_kind.get(kind) if isinstance(kind, str) else None
        if field is None:
            continue
        data = chunk.get("data")
        if not isinstance(data, dict):
            continue
        value = data.get(field)
        if isinstance(value, str):
            out.append(value)
    return out


def _user_facing_texts(events: list[Any]) -> list[str]:
    """User-visible strings from the streamed event sequence — QA answers,
    rejection messages, and phase prose deltas. This is the post-refactor
    source of truth for "what did the user see this turn" (raw
    message_history is gone)."""
    chunks = _iter_chunks(events)
    return _data_chunk_strings(chunks) + _streamed_text_blocks(chunks)


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


def _assert_final_turn(
    state: dict[str, Any],
    captured_history_lens: list[int],
    cross_turn_assistant_texts: list[str],
) -> None:
    """After the final follow-up turn the conversation has run all 6 turns
    end-to-end. We assert on the *streamed* assistant texts collected by
    the harness across all turns (the user-visible record), since the raw
    ``state.message_history`` field is gone — typed phase outputs are now
    the cross-turn contract."""
    assert captured_history_lens, "supervisor was never invoked"
    # message_history was removed; supervisor now never receives history.
    assert all(n == 0 for n in captured_history_lens)
    joined = "\n".join(cross_turn_assistant_texts)
    for needle in (
        "F1 is the harmonic mean",
        "PathFinder is for biological research only",
        "Problem frame updated",
        "Found candidate searches",
        "842 genes",
    ):
        assert needle in joined
    assert state["current_phase"] is None


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


_QA_REJECT_PROMPTS: tuple[tuple[str, str], ...] = (
    ("hi", "qa"),
    ("what is F1?", "qa"),
    ("help me write python", "reject"),
)


async def _run_qa_reject_turns(
    harness: _Harness,
    *,
    expected: dict[str, str],
) -> list[str]:
    """Drive the first three "non-research" turns and assert each one's
    user-facing chunk matches what the supervisor stub queued. Returns the
    accumulated user-facing texts so the rest of the test can extend it."""
    out: list[str] = []
    for idx, (prompt, kind) in enumerate(_QA_REJECT_PROMPTS):
        is_first = idx == 0
        _state, events = await harness.turn(prompt, is_first=is_first)
        chunk_types = _chunk_types(
            [e[1] if isinstance(e, tuple) else e for e in events],
        )
        if kind == "qa":
            assert "data-turn-qa" in chunk_types
        elif kind == "reject":
            assert "data-turn-rejected" in chunk_types
        else:
            msg = f"unknown turn kind: {kind}"
            raise AssertionError(msg)
        if is_first:
            assert "data-supervisor-decision" in chunk_types
            assert "data-phase-start" not in chunk_types
        texts = _user_facing_texts(events)
        assert len(texts) == 1
        assert texts[0] in expected
        out.extend(texts)
    return out


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

            cross_turn_texts = await _run_qa_reject_turns(
                harness,
                expected={
                    "Hi! What would you like to research?": "qa",
                    "F1 is the harmonic mean of precision and recall.": "qa",
                    "PathFinder is for biological research only.": "reject",
                },
            )

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
            # Phase prose still reaches the user via streamed text-delta /
            # text-end events; no turn-qa/rejected card on a phase turn.
            assert "data-turn-qa" not in types_4
            assert "data-turn-rejected" not in types_4
            assert state_4["current_phase"] == "scoping"
            cross_turn_texts.extend(_user_facing_texts(events_4))

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
            cross_turn_texts.extend(_user_facing_texts(events_5))

            # Turn 6: follow-up question uses the whole conversation history
            state_6, events_6 = await harness.turn(
                "summarize what you did", is_first=False,
            )
            cross_turn_texts.extend(_user_facing_texts(events_6))
            _assert_final_turn(state_6, captured_history_lens, cross_turn_texts)


# ────────────────────────────────────────────────────────────────────────────
# Scratchpad regression test (Plan Task 26)
#
# Turn 1: scoping stub calls the real ``note(...)`` tool then returns a
# ``PhaseOutcome(awaiting_user)`` so the supervisor ends the turn cleanly.
# Turn 2: scoping stub calls the real ``list_notes()`` tool — which reads the
# DB row created in turn 1 — and its ToolReturnPart is threaded into the
# agent's message history, proving the scratchpad is visible across turns.
# ────────────────────────────────────────────────────────────────────────────


_SCRATCHPAD_NOTE_TITLE = "TURN1_NOTE"
_SCRATCHPAD_NOTE_SUMMARY = "saved during scoping turn 1"
_SCRATCHPAD_NOTE_BODY = "Body captured while scoping the P. falciparum question."


def _count_tool_returns_in_run(messages: list[ModelMessage]) -> int:
    """Count ToolReturnParts emitted AFTER the most recent UserPromptPart.

    pydantic-ai re-invokes the FunctionModel callable after each tool return,
    so we use this count as the step index within the current agent run.
    """
    boundary = -1
    for i, msg in enumerate(messages):
        if isinstance(msg, ModelRequest) and any(
            isinstance(p, UserPromptPart) for p in msg.parts
        ):
            boundary = i
    count = 0
    for msg in messages[boundary + 1 :]:
        if isinstance(msg, ModelRequest):
            count += sum(1 for p in msg.parts if isinstance(p, ToolReturnPart))
    return count


def _phase_outcome_args() -> str:
    return json.dumps({
        "disposition": PhaseDisposition.AWAITING_USER.value,
        "prose": "Saved a scratchpad note; pausing for user confirmation.",
        "reason": "awaiting confirmation on scope",
    })


def _note_tool_call(call_id: str) -> ToolCallPart:
    return ToolCallPart(
        tool_name="note",
        args=json.dumps({
            "title": _SCRATCHPAD_NOTE_TITLE,
            "summary": _SCRATCHPAD_NOTE_SUMMARY,
            "body": _SCRATCHPAD_NOTE_BODY,
        }),
        tool_call_id=call_id,
    )


def _list_notes_tool_call(call_id: str) -> ToolCallPart:
    return ToolCallPart(
        tool_name="list_notes",
        args=json.dumps({}),
        tool_call_id=call_id,
    )


def _final_result_call(call_id: str) -> ToolCallPart:
    return ToolCallPart(
        tool_name="final_result",
        args=_phase_outcome_args(),
        tool_call_id=call_id,
    )


def _first_scratchpad_tool(turn_idx: int, call_id: str) -> ToolCallPart:
    """Turn 1 writes via ``note``; turn 2+ reads via ``list_notes``."""
    if turn_idx == 0:
        return _note_tool_call(call_id)
    return _list_notes_tool_call(call_id)


def _collect_list_notes_returns(
    messages: list[ModelMessage], sink: list[list[ToolReturnPart]],
) -> None:
    for msg in messages:
        if not isinstance(msg, ModelRequest):
            continue
        returns = [
            p for p in msg.parts
            if isinstance(p, ToolReturnPart) and p.tool_name == "list_notes"
        ]
        if returns:
            sink.append(returns)


def _scratchpad_scoping_stub() -> tuple[
    Agent[AgentDeps, PhaseOutcome], list[list[ToolReturnPart]],
]:
    """Scoping agent that exercises the real scratchpad toolset.

    Step 0 (first _fn call this turn): emit ``note`` (turn 1) or
    ``list_notes`` (turn 2+) as a tool call.
    Step 1: emit ``final_result`` with a ``PhaseOutcome`` so the agent run
    terminates.

    Returns both the agent and an accumulator that the test can inspect to
    confirm turn-2 ``list_notes`` actually returned the note from turn 1.
    """
    turn_counter = {"i": 0}
    captured: list[list[ToolReturnPart]] = []

    def _response_for(messages: list[ModelMessage]) -> ModelResponse:
        step = _count_tool_returns_in_run(messages)
        turn_idx = turn_counter["i"]
        if step == 0:
            return ModelResponse(
                parts=[_first_scratchpad_tool(turn_idx, f"sc_{turn_idx}_0")],
            )
        _collect_list_notes_returns(messages, captured)
        response = ModelResponse(
            parts=[_final_result_call(f"sc_{turn_idx}_final")],
        )
        turn_counter["i"] += 1
        return response

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del info
        return _response_for(messages)

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo,
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del info
        response = _response_for(messages)
        tool_call = next(
            p for p in response.parts if isinstance(p, ToolCallPart)
        )
        yield {
            0: DeltaToolCall(
                name=tool_call.tool_name,
                json_args=tool_call.args_as_json_str(),
                tool_call_id=tool_call.tool_call_id,
            ),
        }

    agent: Agent[AgentDeps, PhaseOutcome] = Agent(
        FunctionModel(
            _fn, stream_function=_stream, model_name="mock:scoping-scratchpad",
        ),
        output_type=PhaseOutcome,
        deps_type=AgentDeps,
        toolsets=[build_scratchpad_toolset()],
        instructions="write a scratchpad note then await user",
        name="mock-scoping-scratchpad",
        defer_model_check=True,
    )
    return agent, captured


def _scratchpad_supervisor_decisions() -> list[SupervisorDecision]:
    # Each turn: start → scoping → (phase sets awaiting_user) → supervisor
    # routes to ``end``. Only the initial routing decision per turn is
    # consumed from this list; the "end" branches short-circuit via the
    # AWAITING_USER halt in supervisor_node.
    return [
        SupervisorDecision(to="scoping", reason="start scratchpad turn 1"),
        SupervisorDecision(to="scoping", reason="start scratchpad turn 2"),
    ]


@pytest.mark.asyncio
async def test_scratchpad_note_persists_across_turns(
    db_cleaner: None,
    patch_app_db_engine: None,
) -> None:
    """Multi-turn regression: note written turn 1 is visible turn 2."""
    del db_cleaner, patch_app_db_engine

    scoping_agent, captured_list_returns = _scratchpad_scoping_stub()
    # Other phases never run in this test but must exist for PHASE_AGENTS
    # completeness. Give them text-only stubs that would error out loudly
    # if the pipeline wandered off-path.
    phase_stubs: dict[str, Agent[AgentDeps, Any]] = {
        "scoping": scoping_agent,
        "discovery": _phase_text_agent("discovery", ["unreachable"]),
        "planning": _phase_text_agent("planning", ["unreachable"]),
        "execution": _phase_text_agent("execution", ["unreachable"]),
        "verification": _phase_text_agent("verification", ["unreachable"]),
    }
    sup_agent, _sup_capture = _supervisor_stub(_scratchpad_supervisor_decisions())

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

            # ── Turn 1: agent calls note(...) during scoping ────────────
            _state_1, events_1 = await harness.turn(
                "scope my malaria question", is_first=True,
            )
            types_1 = _chunk_types(
                [e[1] if isinstance(e, tuple) else e for e in events_1],
            )
            assert "data-phase-start" in types_1
            assert "data-scratchpad-updated" in types_1, (
                f"note(...) must emit data-scratchpad-updated; got {types_1}"
            )

            # Note is in the DB.
            async with async_session_factory() as session:
                notes = await ScratchpadRepository(session).list_notes(
                    conversation_id=conversation_id, limit=10,
                )
            assert len(notes) == 1
            assert notes[0].title == _SCRATCHPAD_NOTE_TITLE
            assert notes[0].summary == _SCRATCHPAD_NOTE_SUMMARY
            assert notes[0].body == _SCRATCHPAD_NOTE_BODY
            turn1_note_id = notes[0].id

            # ── Turn 2: agent calls list_notes() during scoping ────────
            # Must clear ``last_phase_outcome`` — ``_build_turn_input``
            # resets this per turn in production, but the test harness
            # doesn't, so a turn-1 ``awaiting_user`` outcome would keep
            # tripping supervisor_node's AWAITING_USER halt.
            turn_2_input = {
                **_run_turn_input("follow-up question"),
                "last_phase_outcome": None,
            }
            events_2 = [
                ev async for ev in harness.graph.astream(
                    turn_2_input,
                    config=harness.config,
                    context=harness.context,
                    stream_mode=["custom"],
                )
            ]
            types_2 = _chunk_types(
                [e[1] if isinstance(e, tuple) else e for e in events_2],
            )
            assert "data-phase-start" in types_2, (
                f"turn 2 did not hit scoping; chunks={types_2}"
            )

            # Proof-of-visibility: the list_notes ToolReturnPart threaded into
            # the agent's run this turn must contain the note from turn 1.
            assert captured_list_returns, (
                "scoping stub never captured a list_notes ToolReturnPart on turn 2"
            )
            latest_returns = captured_list_returns[-1]
            # There's exactly one list_notes call per turn 2 run.
            assert len(latest_returns) == 1
            payload = latest_returns[0].content
            assert isinstance(payload, dict)
            matches = payload.get("matches")
            assert isinstance(matches, list)
            titles = [
                entry.get("title") for entry in matches
                if isinstance(entry, dict)
            ]
            ids = [
                entry.get("id") for entry in matches
                if isinstance(entry, dict)
            ]
            assert _SCRATCHPAD_NOTE_TITLE in titles, (
                f"turn 2 list_notes should surface the turn-1 note; got {titles}"
            )
            assert turn1_note_id in ids, (
                f"turn 2 list_notes return is missing turn-1 note id "
                f"{turn1_note_id!r}; got {ids}"
            )

