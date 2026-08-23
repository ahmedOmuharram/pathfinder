"""What a one-agent assistant gets when it marks a tool approval-required.

The runtime declares the approval fields and the wire carries the approval
chunks, but the turn graph it ships resolves neither: the call reaches the
user as a stream error. These tests state that as it is.
"""

from __future__ import annotations

from tests.synthetic import (
    APPROVAL_CALL_ID,
    APPROVAL_PROMPT,
    APPROVAL_TOOL,
    SyntheticRuntime,
)

from assistant_core.conversation.event_stream import fetch_chunks_after
from assistant_core.conversation.ui_message_reducer import reduce_chunks

_NO_DEFERRED_OUTPUT = "`DeferredToolRequests` is not among output types"


async def test_an_approval_required_tool_never_reaches_the_user_as_a_card(
    runtime: SyntheticRuntime,
) -> None:
    outcome = await runtime.run(APPROVAL_PROMPT)

    assert "tool-approval-request" not in outcome.types()
    errors = [c for c in outcome.chunks if c["type"] == "error"]
    assert len(errors) == 1
    assert _NO_DEFERRED_OUTPUT in errors[0]["errorText"]


async def test_the_tool_the_user_never_approved_did_not_run(
    runtime: SyntheticRuntime,
) -> None:
    outcome = await runtime.run(APPROVAL_PROMPT)

    _cursor, logged = await fetch_chunks_after(runtime.conversation_id, 0)
    message = reduce_chunks(logged, default_message_id=str(outcome.turn_message_id))

    tool_parts = [p for p in message["parts"] if p["type"] == f"tool-{APPROVAL_TOOL}"]
    assert [p["toolCallId"] for p in tool_parts] == [APPROVAL_CALL_ID]
    assert tool_parts[0]["state"] == "output-error"
    assert "output" not in tool_parts[0]


async def test_the_failed_turn_still_closes_with_finish_then_done(
    runtime: SyntheticRuntime,
) -> None:
    await runtime.run(APPROVAL_PROMPT)

    _cursor, logged = await fetch_chunks_after(runtime.conversation_id, 0)
    types = [c["type"] for c in logged]

    assert types.index("error") < types.index("finish") < types.index("done")
    # The finish reason reports how the turn ended, not that a chunk carried
    # an error: a stream error does not abort the turn.
    assert logged[-2]["finishReason"] == "stop"


async def test_the_turn_graph_leaves_the_approval_state_untouched(
    runtime: SyntheticRuntime,
) -> None:
    await runtime.run(APPROVAL_PROMPT)

    snapshot = await runtime.graph.aget_state(runtime.thread_config())

    # The runtime declares the field an approval would be parked on; the turn
    # graph it ships never writes it, so the channel is absent entirely.
    assert "pending_approval" not in snapshot.values
    assert snapshot.values["approval_responses"] == {}
