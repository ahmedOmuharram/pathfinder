"""A complete assistant built only from the runtime's own code.

Every arc the suite drives runs through this spec, so an assertion that holds
here is an assertion about the runtime and nothing else. The application owns
the turn driver; ``drive_turn`` is the smallest composition the package's
public surfaces allow, and it is where the boundary cuts.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.messages import ModelMessage, ToolCallPart
from pydantic_ai.models import Model
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    DoneChunk,
    FinishChunk,
    StartChunk,
)

from assistant_core.conversation.event_writer import ChatEventWriter, ChatWriter
from assistant_core.graph.runtime import AssistantDeps, TurnContext
from assistant_core.graph.single_agent import single_agent_graph
from assistant_core.graph.stream_events import turn_status_event, turn_stopped_event
from assistant_core.graph.turn_state import TurnState
from assistant_core.models.scripted import (
    RoleMarkers,
    ScriptedModel,
    ScriptedPart,
    called_tool_parts,
    last_user_text,
    scripted_text,
    tool_return_parts,
)
from assistant_core.platform.db import async_session_factory
from assistant_core.spec import (
    AssistantSpec,
    TurnContextRequest,
    TurnStart,
    turn_input,
)

SYNTHETIC_ASSISTANT_ID = "synthetic"
SYNTHETIC_SITE_ID = "synthetic"
SYNTHETIC_MODE = "chat"

ADD_TOOL = "add"
APPROVAL_TOOL = "wipe_everything"
STOP_TOOL = "stop_turn"

ADD_CALL_ID = "call_add"
APPROVAL_CALL_ID = "call_wipe"
STOP_CALL_ID = "call_stop"

# A marker in the user's message picks the arc, so a prompt is the script.
ADD_PROMPT = "please add"
APPROVAL_PROMPT = "please wipe"
STOP_PROMPT = "please stop"
PLAIN_PROMPT = "which sites do you serve"

PREPARING_LABEL = "Preparing context"
EPILOGUE_LABEL = "Turn recorded"


async def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


async def wipe_everything(target: str) -> str:
    """Delete everything under a target."""
    return f"wiped {target}"


async def stop_turn(ctx: RunContext[AssistantDeps]) -> str:
    """Stop the turn that is running."""
    cancel = ctx.deps.cancel_event
    if cancel is not None:
        cancel.set()
    return "stopping"


@dataclass(frozen=True)
class _Arc:
    """One scripted branch: the marker that selects it and the call it makes."""

    marker: str
    tool_name: str
    call_id: str
    args: dict[str, Any]


_ARCS: tuple[_Arc, ...] = (
    _Arc(ADD_PROMPT, ADD_TOOL, ADD_CALL_ID, {"a": 2, "b": 3}),
    _Arc(APPROVAL_PROMPT, APPROVAL_TOOL, APPROVAL_CALL_ID, {"target": "everything"}),
    _Arc(STOP_PROMPT, STOP_TOOL, STOP_CALL_ID, {}),
)


def _next_part(messages: list[ModelMessage]) -> ScriptedPart:
    text = last_user_text(messages)
    called = {part.tool_name for part in called_tool_parts(messages)}
    for arc in _ARCS:
        if arc.marker in text and arc.tool_name not in called:
            return ToolCallPart(
                tool_name=arc.tool_name,
                args=arc.args,
                tool_call_id=arc.call_id,
            )
    returns = tool_return_parts(messages)
    if returns:
        return scripted_text(f"Result: {returns[-1].content}.")
    return scripted_text(f"You said: {text}")


def synthetic_model() -> ScriptedModel:
    return ScriptedModel(
        roles=(RoleMarkers(role="answerer", markers=frozenset({ADD_TOOL})),),
        scripts={"answerer": _next_part},
        unknown=_next_part,
        model_name="synthetic:scripted",
    )


def synthetic_agent() -> Agent[AssistantDeps, str]:
    return Agent(
        synthetic_model().as_function_model(),
        output_type=str,
        deps_type=AssistantDeps,
        instructions="Answer the user.",
        tools=[add, Tool(wipe_everything, requires_approval=True), stop_turn],
        name=SYNTHETIC_ASSISTANT_ID,
    )


@dataclass
class UsageLedger:
    """What the runtime charged, in the order it charged it."""

    charges: list[tuple[UUID, int, Decimal]] = field(default_factory=list)

    async def __call__(self, user_id: UUID, tokens: int, cost_usd: Decimal) -> None:
        self.charges.append((user_id, tokens, cost_usd))

    @property
    def total_tokens(self) -> int:
        return sum(tokens for _user, tokens, _cost in self.charges)


def _deps(state: TurnState, context: TurnContext) -> AssistantDeps:
    return AssistantDeps(
        site_id=context.site_id,
        user_id=context.user_id,
        conversation_id=state.conversation_id,
        db_session_factory=context.db_session_factory,
        memory_store=context.memory_store,
        cancel_event=context.cancel_event,
        retrieved_memories=state.retrieved_memories,
    )


async def _epilogue(conversation_id: UUID) -> list[dict[str, Any]]:
    """The chunks this assistant appends once its graph has finished."""
    del conversation_id
    return [dump_chunk(turn_status_event(label=EPILOGUE_LABEL))]


def synthetic_spec(ledger: UsageLedger) -> AssistantSpec:
    """The synthetic assistant, as the runtime sees any assistant."""

    def build_graph(
        checkpointer: BaseCheckpointSaver[Any],
    ) -> CompiledStateGraph[Any, Any, Any, Any]:
        return single_agent_graph(
            checkpointer=checkpointer,
            state_type=TurnState,
            context_type=TurnContext,
            build_agent=synthetic_agent,
            build_deps=_deps,
            charge_usage=ledger,
        )

    async def build_turn_context(request: TurnContextRequest) -> TurnContext:
        return TurnContext(
            site_id=request.site_id,
            user_id=request.user_id,
            db_session_factory=async_session_factory,
            cancel_event=request.cancel_event,
            memory_store=request.memory_store,
            phase_models=request.phase_models,
            phase_reasoning=request.phase_reasoning,
        )

    return AssistantSpec(
        assistant_id=SYNTHETIC_ASSISTANT_ID,
        build_graph=build_graph,
        build_initial_state=lambda start: TurnState(**start.state_kwargs()),
        build_turn_context=build_turn_context,
        build_mock_model=_mock_model,
        checkpoint_types=(TurnState,),
        memory_kinds=frozenset({"note"}),
        turn_epilogue=_epilogue,
    )


def _mock_model() -> Model:
    return synthetic_model().as_function_model()


def dump_chunk(chunk: BaseChunk) -> dict[str, Any]:
    return chunk.model_dump(by_alias=True, mode="json", exclude_none=True)


async def build_context(
    spec: AssistantSpec,
    *,
    user_id: UUID,
    cancel_event: asyncio.Event | None = None,
) -> TurnContext:
    return await spec.build_turn_context(
        TurnContextRequest(
            conversation=None,
            site_id=SYNTHETIC_SITE_ID,
            user_id=user_id,
            memory_store=None,
            cancel_event=cancel_event or asyncio.Event(),
            phase_models={},
            phase_reasoning={},
        ),
    )


@dataclass(frozen=True, kw_only=True)
class TurnRequest:
    """One turn's inputs for the driver below."""

    spec: AssistantSpec
    graph: CompiledStateGraph[Any, Any, Any, Any]
    writer: ChatWriter
    context: TurnContext
    conversation_id: UUID
    user_id: UUID
    prompt: str = ""
    is_resume: bool = False


@dataclass
class TurnOutcome:
    """What one driven turn produced."""

    turn_message_id: UUID
    chunks: list[dict[str, Any]] = field(default_factory=list)
    start_event_id: int = 0
    cancelled: bool = False

    def types(self) -> list[str]:
        return [str(chunk["type"]) for chunk in self.chunks]

    def finish_reason(self) -> str:
        return "other" if self.cancelled else "stop"


def _turn_start(request: TurnRequest, start_event_id: int) -> TurnStart:
    return TurnStart(
        conversation_id=request.conversation_id,
        user_id=request.user_id,
        site_id=request.context.site_id,
        mode=SYNTHETIC_MODE,
        turn_message_id=request.writer.turn_id,
        turn_start_event_id=start_event_id - 1,
        is_resume=request.is_resume,
        user_message_id=None if request.is_resume else uuid4(),
        user_prompt="" if request.is_resume else request.prompt,
    )


async def _consume(request: TurnRequest, outcome: TurnOutcome) -> None:
    graph_input = turn_input(
        request.spec.build_initial_state(
            _turn_start(request, outcome.start_event_id),
        ),
    )
    config: dict[str, Any] = {
        "configurable": {"thread_id": str(request.conversation_id)},
    }
    async for _mode, payload in request.graph.astream(
        graph_input,
        config=config,
        context=request.context,
        stream_mode=["custom"],
    ):
        chunk = payload["chunk"]
        outcome.chunks.append(chunk)
        await request.writer.write(chunk)


async def drive_turn(request: TurnRequest) -> TurnOutcome:
    """Run one turn end to end, writing every chunk to the durable log.

    The framing is the wire contract: a ``start`` chunk opens the turn and a
    ``finish``/``done`` pair closes it, whatever the turn did in between.
    """
    outcome = TurnOutcome(turn_message_id=request.writer.turn_id)
    outcome.start_event_id = await request.writer.write(
        dump_chunk(StartChunk(message_id=str(request.writer.turn_id))),
    )
    await request.writer.write(
        dump_chunk(turn_status_event(label=PREPARING_LABEL)),
    )
    await _consume(request, outcome)
    outcome.cancelled = request.context.cancel_event.is_set()

    if outcome.cancelled:
        await request.writer.write(dump_chunk(turn_stopped_event()))
    if request.spec.turn_epilogue is not None:
        for chunk in await request.spec.turn_epilogue(request.conversation_id):
            await request.writer.write(chunk)
    await request.writer.write(
        dump_chunk(FinishChunk(finish_reason=outcome.finish_reason())),
    )
    await request.writer.write(dump_chunk(DoneChunk()))
    return outcome


@dataclass(frozen=True, kw_only=True)
class SyntheticRuntime:
    """One installed synthetic assistant and the thread its turns run on."""

    spec: AssistantSpec
    graph: CompiledStateGraph[Any, Any, Any, Any]
    ledger: UsageLedger
    conversation_id: UUID
    user_id: UUID

    async def run(
        self,
        prompt: str = "",
        *,
        is_resume: bool = False,
        cancel: asyncio.Event | None = None,
    ) -> TurnOutcome:
        """Drive one turn, with its own message id and its own cancel event."""
        writer = ChatEventWriter(
            conversation_id=self.conversation_id,
            turn_id=uuid4(),
        )
        context = await build_context(
            self.spec,
            user_id=self.user_id,
            cancel_event=cancel,
        )
        return await drive_turn(
            TurnRequest(
                spec=self.spec,
                graph=self.graph,
                writer=writer,
                context=context,
                conversation_id=self.conversation_id,
                user_id=self.user_id,
                prompt=prompt,
                is_resume=is_resume,
            ),
        )

    def thread_config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": str(self.conversation_id)}}
