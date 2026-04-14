from __future__ import annotations

from uuid import uuid4

from pydantic_ai import Agent
from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage
from pydantic_ai.ui.vercel_ai.response_types import (
    DoneChunk,
    FinishChunk,
    StartChunk,
    TextDeltaChunk,
    TextEndChunk,
    TextStartChunk,
    ToolInputAvailableChunk,
    ToolInputDeltaChunk,
    ToolInputErrorChunk,
    ToolInputStartChunk,
    ToolOutputAvailableChunk,
)

from pathfinder.ai.graph.nodes import (
    build_run_input,
    discovery_node,
    execution_node,
    is_chunk_to_drop,
    model_id,
    planning_node,
    scoping_node,
    verification_node,
)
from pathfinder.ai.graph.state import PipelineState


def _state() -> PipelineState:
    return PipelineState(
        chat_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_message_id=uuid4(),
        user_prompt="find drug targets",
        user_parts=[{"type": "text", "text": "find drug targets"}],
    )


def test_build_run_input_produces_submit_message() -> None:
    state = _state()
    run_input = build_run_input(state)
    assert isinstance(run_input, SubmitMessage)
    assert run_input.id == str(state.chat_id)
    assert run_input.trigger == "submit-message"
    assert len(run_input.messages) == 1
    msg = run_input.messages[0]
    assert msg.role == "user"
    assert msg.id == str(state.user_message_id)


def test_build_run_input_handles_missing_user_message_id() -> None:
    state = _state().model_copy(update={"user_message_id": None})
    run_input = build_run_input(state)
    assert run_input.messages[0].id  # auto-assigned uuid
    assert run_input.messages[0].id != ""


def test_model_id_handles_string_models() -> None:
    agent: Agent[None, str] = Agent(
        "openai:gpt-4.1-mini",
        output_type=str,
        name="t",
        defer_model_check=True,
    )
    assert model_id(agent) == "openai:gpt-4.1-mini"


def test_is_chunk_to_drop_drops_start_finish_done() -> None:
    suppressed: set[str] = set()
    assert is_chunk_to_drop(
        StartChunk(message_id="m"), suppressed
    )
    assert is_chunk_to_drop(FinishChunk(finish_reason="stop"), suppressed)
    assert is_chunk_to_drop(DoneChunk(), suppressed)


def test_is_chunk_to_drop_marks_final_result_id_as_suppressed() -> None:
    suppressed: set[str] = set()
    is_chunk_to_drop(
        ToolInputStartChunk(
            tool_call_id="call_1", tool_name="final_result"
        ),
        suppressed,
    )
    assert "call_1" in suppressed


def test_is_chunk_to_drop_drops_followups_for_suppressed_tool() -> None:
    suppressed: set[str] = {"call_1"}
    assert is_chunk_to_drop(
        ToolInputDeltaChunk(tool_call_id="call_1", input_text_delta="."),
        suppressed,
    )
    assert is_chunk_to_drop(
        ToolInputAvailableChunk(
            tool_call_id="call_1", tool_name="final_result", input={}
        ),
        suppressed,
    )
    assert is_chunk_to_drop(
        ToolInputErrorChunk(
            tool_call_id="call_1",
            tool_name="final_result",
            input={},
            error_text="bad",
        ),
        suppressed,
    )
    assert is_chunk_to_drop(
        ToolOutputAvailableChunk(tool_call_id="call_1", output="ok"),
        suppressed,
    )


def test_is_chunk_to_drop_keeps_normal_text_chunks() -> None:
    suppressed: set[str] = set()
    assert not is_chunk_to_drop(TextStartChunk(id="t1"), suppressed)
    assert not is_chunk_to_drop(
        TextDeltaChunk(id="t1", delta="hello"), suppressed
    )
    assert not is_chunk_to_drop(TextEndChunk(id="t1"), suppressed)


def test_is_chunk_to_drop_keeps_unsuppressed_tool_chunks() -> None:
    suppressed: set[str] = set()
    assert not is_chunk_to_drop(
        ToolInputStartChunk(tool_call_id="call_1", tool_name="get_strategy"),
        suppressed,
    )
    assert not is_chunk_to_drop(
        ToolOutputAvailableChunk(tool_call_id="call_2", output="ok"),
        suppressed,
    )


def test_phase_node_functions_exist() -> None:
    assert callable(scoping_node)
    assert callable(discovery_node)
    assert callable(planning_node)
    assert callable(execution_node)
    assert callable(verification_node)
