"""The deferred-tool (consult_user) resume must replay the FULL run history.

When the Lead's first action is the deferred tool, ``new_messages()`` holds
only the assistant ``ToolCallPart`` with no leading ``ModelRequest`` — which
pydantic-ai rejects on resume as 'message history is empty'. ``_absorb_run_result``
must capture ``all_messages()`` (request + tool call) into ``prior_messages_json``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.usage import RunUsage

from pathfinder.ai.graph._lead_capture import _LeadRunCapture
from pathfinder.ai.graph.lead_node import _absorb_run_result


class _FakeResult:
    def __init__(
        self,
        *,
        all_msgs: list[Any],
        new_msgs: list[Any],
        output: Any,
    ) -> None:
        self._all = all_msgs
        self._new = new_msgs
        self.output = output
        self.response = SimpleNamespace(
            finish_reason=None,
            model_name="openai:gpt-5-mini",
            provider_name=None,
            provider_url=None,
        )
        self.usage = RunUsage()

    def all_messages(self) -> list[Any]:
        return self._all

    def new_messages(self) -> list[Any]:
        return self._new


def test_deferred_resume_history_includes_user_request() -> None:
    call = ToolCallPart(
        tool_name="consult_user", args={"questions": []}, tool_call_id="c1"
    )
    user_req = ModelRequest(parts=[UserPromptPart(content="build it")])
    consult_resp = ModelResponse(parts=[call])
    result = _FakeResult(
        # new_messages() lacks the leading ModelRequest (Lead's first move was
        # the deferred tool); all_messages() carries it.
        all_msgs=[user_req, consult_resp],
        new_msgs=[consult_resp],
        output=DeferredToolRequests(approvals=[call]),
    )
    capture = _LeadRunCapture()
    event: Any = SimpleNamespace(result=result)
    _absorb_run_result(event, capture)

    assert capture.pending_approval is not None
    history = ModelMessagesTypeAdapter.validate_json(
        capture.pending_approval.prior_messages_json
    )
    # The fix: the persisted resume history starts with the user request, so
    # pydantic-ai can match the deferred result to the consult tool call.
    assert len(history) == 2
    assert isinstance(history[0], ModelRequest)
    assert isinstance(history[1], ModelResponse)
