"""Validate / Research specialist graph nodes."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import nullcontext
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic_ai import Agent, AgentRunResultEvent
from pydantic_ai.messages import (
    AgentStreamEvent,
    ModelMessage,
    ModelResponse,
    TextPart,
)
from pydantic_ai.usage import RunUsage
from sqlalchemy.exc import SQLAlchemyError

from pathfinder.ai.conversation.vercel_adapter import PhaseStreamEmitter
from pathfinder.ai.cost import cost_for_run
from pathfinder.ai.graph.nodes import (
    _convert_assistant_parts,
    _data_part,
    _dump_parts,
    _emit_chunk,
    _split_agent_model,
    _text_part,
)
from pathfinder.ai.graph.runtime import AgentDeps, Context, build_node_deps
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.graph.stream_events import turn_usage_event
from pathfinder.ai.specialists.agents import research_agent, validate_agent
from pathfinder.ai.specialists.types import SpecialistKind, SpecialistMode
from pathfinder.persistence.repositories import MessagesRepository
from pathfinder.persistence.repositories.conversation import (
    ConversationRepository,
    ConversationUpdate,
)
from pathfinder.platform.config import get_settings
from pathfinder.platform.logging import get_logger
from pathfinder.services import quota as quota_service

logger = get_logger(__name__)

_FINALIZE: Literal["finalize_turn"] = "finalize_turn"


def _agent_for(kind: SpecialistKind) -> Agent[AgentDeps, str]:
    if kind == "validate":
        return validate_agent
    return research_agent


def _resolve_specialist_agent_model(mode: SpecialistMode) -> str | None:
    """Return the catalog model id to override the agent with, or None.

    Empty / missing model id falls back to the agent's hardcoded default.
    The mock-LLM E2E stack overrides agents at a different layer, so we
    skip the override there.
    """
    if get_settings().pathfinder_chat_provider.strip().lower() == "mock":
        return None
    return mode.model_id or None


def _build_specialist_deps(
    state: PipelineState, runtime_context: Context | None,
) -> AgentDeps:
    """Specialist deps — same shape as a normal phase but no plan / scratchpad."""
    if runtime_context is None:
        msg = "specialist node requires a runtime context"
        raise RuntimeError(msg)
    return build_node_deps(state, runtime_context, memories=state.retrieved_memories)


async def _charge_specialist_token_delta(
    *,
    runtime_context: Context | None,
    state: PipelineState,
    usage: RunUsage,
    charged: dict[str, int | Decimal],
    writer: Any,
    agent_model: str,
) -> None:
    """Bill the user's quota for tokens accumulated since the last call."""
    if runtime_context is None:
        return
    delta_input = usage.input_tokens - int(charged["input"])
    delta_output = usage.output_tokens - int(charged["output"])
    delta_cache_read = usage.cache_read_tokens - int(charged["cache_read"])
    delta_cache_write = usage.cache_write_tokens - int(charged["cache_write"])
    delta_tokens = (
        delta_input + delta_output + delta_cache_read + delta_cache_write
    )
    if delta_tokens <= 0:
        return
    provider_name, model_name = _split_agent_model(agent_model)
    delta_cost = cost_for_run(
        usage=RunUsage(
            input_tokens=delta_input,
            output_tokens=delta_output,
            cache_read_tokens=delta_cache_read,
            cache_write_tokens=delta_cache_write,
        ),
        model_name=model_name,
        provider_name=provider_name,
        provider_url=None,
    )
    try:
        async with runtime_context.db_session_factory() as session:
            if state.user_id is not None:
                await quota_service.accumulate(
                    session,
                    user_id=state.user_id,
                    tokens=delta_tokens,
                    cost_usd=delta_cost,
                )
            await session.commit()
    except SQLAlchemyError:
        logger.warning(
            "specialist token delta accumulate failed",
            user_id=str(state.user_id),
            conversation_id=str(state.conversation_id),
        )
        return
    charged["input"] = int(charged["input"]) + delta_input
    charged["output"] = int(charged["output"]) + delta_output
    charged["cache_read"] = int(charged["cache_read"]) + delta_cache_read
    charged["cache_write"] = int(charged["cache_write"]) + delta_cache_write
    charged["cost"] = Decimal(str(charged["cost"])) + delta_cost
    total_charged_tokens = (
        int(charged["input"])
        + int(charged["output"])
        + int(charged["cache_read"])
        + int(charged["cache_write"])
    )
    _emit_chunk(
        writer,
        turn_usage_event(
            total_tokens=state.turn_total_tokens + total_charged_tokens,
            cost_usd=str(state.turn_total_cost_usd + Decimal(str(charged["cost"]))),
        ),
    )


@dataclass
class _DrainArgs:
    agent: Agent[AgentDeps, str]
    user_prompt: str
    deps: AgentDeps
    writer: Any
    emitter: PhaseStreamEmitter
    runtime_context: Context | None
    state: PipelineState
    agent_model: str


async def _drain_agent(args: _DrainArgs) -> tuple[list[ModelMessage], str, RunUsage]:
    new_messages: list[ModelMessage] = []
    final_text = ""
    usage_acc = RunUsage()
    charged: dict[str, int | Decimal] = {
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_write": 0,
        "cost": Decimal(0),
    }

    async def _events() -> AsyncGenerator[AgentStreamEvent | AgentRunResultEvent[Any]]:
        async for event in args.agent.run_stream_events(
            args.user_prompt, deps=args.deps, usage=usage_acc,
        ):
            if isinstance(event, AgentRunResultEvent):
                run_result = event.result
                new_messages.extend(run_result.new_messages())
                output = run_result.output
                if isinstance(output, str):
                    nonlocal final_text
                    final_text = output
            await _charge_specialist_token_delta(
                runtime_context=args.runtime_context,
                state=args.state,
                usage=usage_acc,
                charged=charged,
                writer=args.writer,
                agent_model=args.agent_model,
            )
            yield event

    async for chunk in args.emitter.chunks(_events()):
        _emit_chunk(args.writer, chunk)
    return new_messages, final_text, usage_acc


async def _persist_assistant_message(
    *,
    runtime_context: Context | None,
    state: PipelineState,
    parts: list[Any],
) -> None:
    if runtime_context is None or not parts:
        return
    async with runtime_context.db_session_factory() as session:
        try:
            await MessagesRepository(session).upsert_message(
                message_id=state.turn_message_id,
                conversation_id=state.conversation_id,
                role="assistant",
                parts=_dump_parts(parts),
                metadata={
                    "traceId": state.turn_trace_id,
                    "createdAt": state.turn_created_at,
                    "siteId": state.site_id,
                    "mode": state.mode,
                },
            )
            await session.commit()
        except SQLAlchemyError:
            logger.warning(
                "specialist message persist failed",
                conversation_id=str(state.conversation_id),
            )


async def clear_specialist_mode(
    *, runtime_context: Context | None, conversation_id: Any,
) -> None:
    """Clear ``Conversation.specialist_mode`` — used by the exit endpoint
    and by the resume handler when ``exit_specialist`` interrupts."""
    if runtime_context is None:
        return
    async with runtime_context.db_session_factory() as session:
        try:
            await ConversationRepository(session).update_conversation(
                conversation_id,
                ConversationUpdate(
                    specialist_mode=None,
                    specialist_mode_set=True,
                ),
            )
            await session.commit()
        except SQLAlchemyError:
            logger.warning(
                "specialist mode clear failed",
                conversation_id=str(conversation_id),
            )


def _last_text(messages: list[ModelMessage]) -> str:
    for msg in reversed(messages):
        if not isinstance(msg, ModelResponse):
            continue
        for part in msg.parts:
            if isinstance(part, TextPart) and part.content.strip():
                return part.content
    return ""


async def _run_specialist(
    state: PipelineState, runtime: Runtime[Context], *, kind: SpecialistKind,
) -> Command[Literal["finalize_turn"]]:
    if state.specialist_mode is None:
        msg = (
            f"specialist '{kind}' invoked with state.specialist_mode is None"
        )
        raise RuntimeError(msg)
    mode = state.specialist_mode

    writer = get_stream_writer()
    deps = _build_specialist_deps(state, runtime.context)

    base_agent = _agent_for(kind)
    model_override = _resolve_specialist_agent_model(mode)
    override_ctx = (
        base_agent.override(model=model_override)
        if model_override is not None
        else nullcontext()
    )
    agent_model = model_override or _agent_model_id(base_agent)

    turn_message_id = uuid4()
    emitter = PhaseStreamEmitter(message_id=str(turn_message_id))
    with override_ctx:
        new_messages, final_text, usage = await _drain_agent(
            _DrainArgs(
                agent=base_agent,
                user_prompt=state.user_prompt or "(empty)",
                deps=deps,
                writer=writer,
                emitter=emitter,
                runtime_context=runtime.context,
                state=state,
                agent_model=agent_model,
            ),
        )

    new_parts: list[Any] = [
        _data_part(
            "data-specialist-turn-start",
            {"kind": kind, "modelId": mode.model_id},
        ),
        *_convert_assistant_parts(new_messages),
    ]

    prose = final_text or _last_text(new_messages)
    if prose and prose not in {p.text for p in new_parts if hasattr(p, "text")}:
        new_parts.append(_text_part(prose))

    await _persist_assistant_message(
        runtime_context=runtime.context, state=state, parts=new_parts,
    )

    provider_name, model_name = _split_agent_model(agent_model)
    turn_cost = cost_for_run(
        usage=usage,
        model_name=model_name,
        provider_name=provider_name,
        provider_url=None,
    )
    update: dict[str, Any] = {
        "turn_message_parts": [*state.turn_message_parts, *new_parts],
        "last_assistant_prose": prose,
        "turn_total_tokens": state.turn_total_tokens + usage.total_tokens,
        "turn_total_cost_usd": state.turn_total_cost_usd + turn_cost,
    }
    return Command(goto=_FINALIZE, update=update)


def _agent_model_id(agent: Agent[Any, Any]) -> str:
    model = agent.model
    if model is None:
        return ""
    if isinstance(model, str):
        return model
    return getattr(model, "model_id", "")


async def validate_node(
    state: PipelineState, runtime: Runtime[Context],
) -> Command[Literal["finalize_turn"]]:
    return await _run_specialist(state, runtime, kind="validate")


async def research_node(
    state: PipelineState, runtime: Runtime[Context],
) -> Command[Literal["finalize_turn"]]:
    return await _run_specialist(state, runtime, kind="research")


__all__ = [
    "clear_specialist_mode",
    "research_node",
    "validate_node",
]
