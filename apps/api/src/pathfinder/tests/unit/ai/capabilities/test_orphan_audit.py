from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic_ai.capabilities.abstract import CapabilityPosition
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.tools import RunContext

from pathfinder.ai.capabilities.orphan_audit import OrphanToolAuditor


def _ctx() -> RunContext:  # type: ignore[type-arg]
    ctx = MagicMock(spec=RunContext)
    ctx.deps = MagicMock()
    ctx.deps.conversation_id = "conv-x"
    return ctx


def _req_ctx(messages: list) -> ModelRequestContext:  # type: ignore[type-arg]
    req = MagicMock(spec=ModelRequestContext)
    req.messages = messages
    return req


def _pair(call_id: str) -> tuple[ModelResponse, ModelRequest]:
    return (
        ModelResponse(
            parts=[ToolCallPart(
                tool_name="x", args={}, tool_call_id=call_id,
            )],
        ),
        ModelRequest(
            parts=[ToolReturnPart(
                tool_name="x", content="ok", tool_call_id=call_id,
            )],
        ),
    )


def test_get_ordering_is_innermost() -> None:
    auditor = OrphanToolAuditor()
    ordering = auditor.get_ordering()
    position: CapabilityPosition = "innermost"
    assert ordering.position == position


@pytest.mark.asyncio
async def test_passthrough_when_paired() -> None:
    call, ret = _pair("c1")
    messages = [ModelRequest(parts=[UserPromptPart(content="hi")]), call, ret]
    auditor = OrphanToolAuditor()
    req = _req_ctx(list(messages))
    out = await auditor.before_model_request(_ctx(), req)
    assert out.messages is req.messages
    assert len(out.messages) == 3


@pytest.mark.asyncio
async def test_repairs_orphan_call_with_placeholder_return() -> None:
    orphan_call = ModelResponse(
        parts=[ToolCallPart(
            tool_name="x", args={}, tool_call_id="orphan_c",
        )],
    )
    messages = [
        ModelRequest(parts=[UserPromptPart(content="hi")]),
        orphan_call,
    ]
    auditor = OrphanToolAuditor()
    req = _req_ctx(list(messages))
    out = await auditor.before_model_request(_ctx(), req)
    has_return = False
    for msg in out.messages:
        for part in msg.parts:
            if isinstance(part, ToolReturnPart) and part.tool_call_id == "orphan_c":
                has_return = True
    assert has_return, "orphan call must be paired with a placeholder return"


@pytest.mark.asyncio
async def test_drops_orphan_return() -> None:
    orphan_return = ModelRequest(
        parts=[ToolReturnPart(
            tool_name="x", content="late", tool_call_id="orphan_r",
        )],
    )
    messages = [
        ModelRequest(parts=[UserPromptPart(content="hi")]),
        orphan_return,
    ]
    auditor = OrphanToolAuditor()
    req = _req_ctx(list(messages))
    out = await auditor.before_model_request(_ctx(), req)
    for msg in out.messages:
        for part in msg.parts:
            if isinstance(part, ToolReturnPart):
                assert part.tool_call_id != "orphan_r"
