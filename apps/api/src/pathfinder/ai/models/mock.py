"""Deterministic LLM mock — emits a single LeadResponse via FunctionModel."""
from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from pathfinder.ai.lead.lead_agent import LeadResponse

_MOCK_PROSE = "[mock] Investigation paused — supply more context or rephrase."


def _lead_response_payload() -> dict[str, object]:
    return LeadResponse(prose=_MOCK_PROSE, next_state="await_user").model_dump(
        by_alias=True, mode="json",
    )


def _final_result_part() -> ToolCallPart:
    return ToolCallPart(
        tool_name="final_result",
        args=_lead_response_payload(),
        tool_call_id=f"mock_lead_final_{uuid4().hex[:12]}",
    )


def _mock_function(
    messages: list[ModelMessage], info: AgentInfo,
) -> ModelResponse:
    del messages, info
    return ModelResponse(parts=[_final_result_part()])


async def _mock_stream_function(
    messages: list[ModelMessage], info: AgentInfo,
) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
    del messages, info
    part = _final_result_part()
    yield {
        0: DeltaToolCall(
            name=part.tool_name,
            json_args=part.args_as_json_str(),
            tool_call_id=part.tool_call_id,
        ),
    }


def get_mock_model() -> FunctionModel:
    return FunctionModel(
        _mock_function,
        stream_function=_mock_stream_function,
        model_name="mock:deterministic",
    )


__all__ = ["get_mock_model"]
