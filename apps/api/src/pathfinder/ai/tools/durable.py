"""Primitives for durable (long-running) agent tools.

Durable tools dispatch their work to the Procrastinate worker and stream
progress back to the chat via ``TaskProgressEmitter``. The emitter persists
rows to ``task_progress`` and publishes a LISTEN/NOTIFY event on
``task_progress:<conversation_id>`` so the dispatcher can resume/flush progress into
the UI message stream without polling.

``@durable_tool`` wraps an agent-side tool so calling it submits a
Procrastinate job and then ``interrupt()``s the graph. The real work runs on
the worker via the ``TOOL_REGISTRY`` mapping.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, ParamSpec, Protocol, TypeVar, cast
from uuid import UUID

from langgraph.config import get_stream_writer
from langgraph.types import interrupt
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    model_validator,
)
from pydantic_ai.tools import RunContext
from pydantic_ai.ui.vercel_ai.response_types import BaseChunk

from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.payloads import DurableTaskPayload
from pathfinder.services.tasks.background import create_background_task

P = ParamSpec("P")
R = TypeVar("R")


class DurableOutcome(BaseModel):
    """The payload the worker resumes a durable tool with."""

    model_config = ConfigDict(extra="ignore")

    status: str = ""
    result: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _mapping_only(cls, raw: object) -> object:
        return raw if isinstance(raw, dict) else {}

    @property
    def succeeded(self) -> bool:
        """Whether the worker reported a result to describe."""
        return self.status == "success"


ChunkBuilder = Callable[[Any, UUID, str | None], list[BaseChunk]]


class DurableIdentity(Protocol):
    """What a durable dispatch needs from an agent's deps."""

    @property
    def conversation_id(self) -> UUID | None: ...
    @property
    def user_id(self) -> UUID | None: ...


def durable_tool(
    *,
    tool_name: str,
    estimated_duration_seconds: int,
    chunks_from_result: ChunkBuilder | None = None,
) -> Callable[
    [Callable[P, Awaitable[R]]],
    Callable[P, Awaitable[R]],
]:
    """Mark an agent-side pydantic-ai tool as durable.

    ``chunks_from_result`` lets a tool emit chat-visible SSE chunks built
    from the resumed payload - runs at resume time inside the LangGraph
    node, so chunks are persisted/replayed via the same writer as the
    agent's own stream output.
    """

    def decorator(
        fn: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[R]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            ctx, tool_args = _parse_invocation(args, kwargs)
            deps = _require_durable_deps(ctx.deps)

            task_id = await create_background_task(
                conversation_id=deps.conversation_id,
                user_id=deps.user_id,
                tool_name=tool_name,
                args=tool_args,
                estimated_duration_seconds=estimated_duration_seconds,
            )
            # The worker resumes the graph on the conversation's checkpoint
            # thread, so this job takes the same lock a chat turn takes.
            task = procrastinate_app.configure_task(
                name=f"durable:{tool_name}",
                queue="verification",
                lock=str(deps.conversation_id),
            )
            dispatched_payload = DurableTaskPayload.from_context(
                task_id=task_id,
                thread_id=deps.conversation_id,
                args=tool_args,
            )
            await task.defer_async(
                **dispatched_payload.model_dump(mode="json", by_alias=True),
            )

            resumed = interrupt(
                {
                    "kind": "durable_task",
                    "task_id": str(task_id),
                    "tool_name": tool_name,
                    "estimated_duration_seconds": estimated_duration_seconds,
                }
            )
            if chunks_from_result is not None:
                writer = get_stream_writer()
                for chunk in chunks_from_result(resumed, task_id, ctx.tool_call_id):
                    writer(
                        {
                            "chunk": chunk.model_dump(
                                by_alias=True,
                                mode="json",
                                exclude_none=True,
                            ),
                        },
                    )
            return cast("R", resumed)

        return wrapper

    return decorator


@dataclass(frozen=True)
class _DurableDeps:
    """The identity a durable dispatch resolved."""

    conversation_id: UUID
    user_id: UUID


def _require_durable_deps(deps: DurableIdentity) -> _DurableDeps:
    if deps.conversation_id is None:
        msg = "durable_tool requires conversation_id on the agent's deps"
        raise RuntimeError(msg)
    if deps.user_id is None:
        msg = "durable_tool requires user_id on the agent's deps"
        raise RuntimeError(msg)
    return _DurableDeps(conversation_id=deps.conversation_id, user_id=deps.user_id)


def _parse_invocation(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[RunContext[DurableIdentity], dict[str, Any]]:
    if not args:
        msg = "durable_tool requires RunContext[DurableIdentity] as first argument"
        raise RuntimeError(msg)
    ctx = cast("RunContext[DurableIdentity]", args[0])
    tool_args: dict[str, Any] = {
        "args": [_to_jsonable(v) for v in args[1:]],
        "kwargs": {k: _to_jsonable(v) for k, v in kwargs.items()},
    }
    return ctx, tool_args


_ANY_JSON: TypeAdapter[Any] = TypeAdapter(Any)


def _to_jsonable(value: Any) -> Any:
    return _ANY_JSON.dump_python(value, mode="json")
