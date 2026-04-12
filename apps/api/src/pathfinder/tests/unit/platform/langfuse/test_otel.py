"""Tests for Langfuse OTEL attribute helpers."""

from unittest.mock import MagicMock

from pathfinder.platform.langfuse.otel import (
    LangfuseTraceAttributes,
    LangfuseTraceContext,
    propagate_langfuse_trace_context,
    set_langfuse_observation_attributes,
    set_langfuse_trace_attributes,
)


def test_set_langfuse_trace_attributes_sets_root_fields() -> None:
    span = MagicMock()

    set_langfuse_trace_attributes(
        span,
        LangfuseTraceAttributes(
            as_root=True,
            name="chat.new_strategy",
            input_value={"message": "find transporters"},
            output_value="Done",
        ),
        trace_ctx=LangfuseTraceContext(
            user_id="user-1",
            session_id="stream-1",
            tags=("plasmodb", "chat"),
            metadata={"intent": "new_strategy", "tool_calls": 3},
            release="1.2.3",
            environment="development",
        ),
    )

    actual_calls = [call.args for call in span.set_attribute.call_args_list]
    expected_calls = {
        ("langfuse.internal.as_root", True),
        ("langfuse.observation.type", "span"),
        ("langfuse.trace.name", "chat.new_strategy"),
        ("user.id", "user-1"),
        ("session.id", "stream-1"),
        ("langfuse.release", "1.2.3"),
        ("langfuse.environment", "development"),
        ("langfuse.trace.input", '{"message":"find transporters"}'),
        ("langfuse.trace.output", "Done"),
        ("langfuse.trace.metadata.intent", "new_strategy"),
        ("langfuse.trace.metadata.tool_calls", "3"),
    }
    for expected in expected_calls:
        assert expected in actual_calls


def test_propagate_langfuse_trace_context_sets_stable_fields() -> None:
    span = MagicMock()

    propagate_langfuse_trace_context(
        span,
        LangfuseTraceContext(
            user_id="user-1",
            session_id="stream-1",
            tags=("plasmodb", "chat", "new_strategy"),
            metadata={"turn_id": "op_123", "message_group_id": "group-1"},
            release="1.2.3",
            environment="development",
        ),
    )

    actual_calls = [call.args for call in span.set_attribute.call_args_list]
    expected_calls = [
        ("user.id", "user-1"),
        ("session.id", "stream-1"),
        ("langfuse.trace.tags", ["plasmodb", "chat", "new_strategy"]),
        ("langfuse.trace.metadata.turn_id", "op_123"),
        ("langfuse.trace.metadata.message_group_id", "group-1"),
        ("langfuse.release", "1.2.3"),
        ("langfuse.environment", "development"),
    ]
    for expected in expected_calls:
        assert expected in actual_calls


def test_set_langfuse_observation_attributes_serializes_metadata() -> None:
    span = MagicMock()

    set_langfuse_observation_attributes(
        span,
        observation_type="agent",
        input_value={"phase": "scoping"},
        output_value={"assistantMessage": "Need one answer"},
        metadata={"prompt_bundle": "system@2,safety@local", "tool_calls": 1},
    )

    actual_calls = [call.args for call in span.set_attribute.call_args_list]
    expected_calls = {
        ("langfuse.observation.type", "agent"),
        ("langfuse.observation.input", '{"phase":"scoping"}'),
        (
            "langfuse.observation.output",
            '{"assistantMessage":"Need one answer"}',
        ),
        (
            "langfuse.observation.metadata.prompt_bundle",
            "system@2,safety@local",
        ),
        ("langfuse.observation.metadata.tool_calls", "1"),
    }
    for expected in expected_calls:
        assert expected in actual_calls
