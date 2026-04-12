"""Tests for streaming pipeline utilities: event emission, usage merging,
tool-call arg parsing, tag stripper edge cases, and TurnCounters.

NOTE: allowed_tools_for_step and dependency ordering are tested in
test_execution_agent.py — not duplicated here.
"""

import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartStartEvent,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.usage import RunUsage

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.orchestration.classifier import Intent
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.phase_results import (
    PhaseDecision,
    ProblemFrame,
    ScopingResult,
)
from pathfinder.ai.orchestration.pipeline import create_pipeline
from pathfinder.ai.prompts.loader import PromptBundle
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.context import operation_id_ctx, stream_id_ctx
from pathfinder.platform.langfuse.prompts import LoadedPrompt
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.streaming.events import (
    emit_delta,
    emit_thoughts,
    parse_tool_call_args,
)
from pathfinder.services.chat.streaming.node_streaming import (
    StreamMessageContext,
    TurnCounters,
    handle_text_part_start,
    merge_usage,
    stream_call_tools,
)
from pathfinder.services.chat.streaming.phase_runner import (
    PhaseConfig,
    _run_phase_inner,
)
from pathfinder.services.chat.streaming.tag_stripper import StreamingTagStripper
from pathfinder.services.chat.streaming.turn_execution import (
    configure_state_machine_for_intent,
)
from pathfinder.services.chat.streaming.turn_lifecycle import (
    _emit_phase_status,
    _finalize_stream,
    _handle_pipeline_error,
)
from pathfinder.services.chat.streaming.turn_telemetry import (
    PhaseEventContext,
    PhaseSpanContext,
    PhaseTimingTracker,
    TurnFailureContext,
    TurnLatencySummary,
    TurnRuntimeTelemetry,
    TurnTelemetryContext,
)
from pathfinder.services.chat.streaming.turn_trace_context import (
    _set_phase_span_attributes,
    _turn_trace_metadata,
)

# ── Helpers ────────────────────────────────────────────────────────────────


def _drain_queue(queue: asyncio.Queue[JSONObject]) -> list[JSONObject]:
    """Synchronously drain all items from a queue."""
    items: list[JSONObject] = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


def _make_deps(site_id: str = "plasmodb") -> AgentDeps:
    return AgentDeps(
        site_id=site_id,
        strategy_session=StrategySession(site_id=site_id),
        agent_state=AgentToolState(),
    )


def test_configure_state_machine_for_discovery_resume_skips_scoping() -> None:
    sm = create_pipeline()

    configure_state_machine_for_intent(
        sm,
        Intent.QUESTION,
        resume_phase="discovery",
    )

    assert sm.current_phase == "discovery"


def test_configure_state_machine_for_planning_resume_skips_to_planning() -> None:
    sm = create_pipeline()

    configure_state_machine_for_intent(
        sm,
        Intent.QUESTION,
        resume_phase="planning",
    )

    assert sm.current_phase == "planning"


class _FakeStreamContext:
    def __init__(self, events: list[Any]) -> None:
        self._events = events

    async def __aenter__(self) -> "_FakeStreamContext":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def __aiter__(self) -> "_FakeStreamContext":
        self._iter = iter(self._events)
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _FakeCallToolsNode:
    def __init__(self, events: list[Any]) -> None:
        self._events = events

    def stream(self, _ctx: object) -> _FakeStreamContext:
        return _FakeStreamContext(self._events)


class _FakeRun:
    def __init__(self, nodes: list[object]) -> None:
        self._nodes = nodes
        self.ctx = object()

    def __aiter__(self) -> "_FakeRun":
        self._iter = iter(self._nodes)
        return self

    async def __anext__(self) -> object:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    def usage(self) -> RunUsage:
        return RunUsage()

    def new_messages(self) -> list[object]:
        return []


class _FakeAgentIterContext:
    def __init__(self, run: _FakeRun) -> None:
        self._run = run

    async def __aenter__(self) -> _FakeRun:
        return self._run

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class _FakeAgent:
    def __init__(self, run: _FakeRun) -> None:
        self._run = run

    def iter(self, *_args: object, **_kwargs: object) -> _FakeAgentIterContext:
        return _FakeAgentIterContext(self._run)


# ── emit_delta / emit_thoughts ──────────────────────────────────────────


@pytest.mark.asyncio
async def testemit_delta_puts_correct_event_type() -> None:
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    await emit_delta(queue, "msg-1", "Hello world")

    events = _drain_queue(queue)
    assert len(events) == 1
    assert events[0]["type"] == "assistant_delta"
    data = cast("JSONObject", events[0]["data"])
    assert data["delta"] == "Hello world"
    assert data["messageId"] == "msg-1"


@pytest.mark.asyncio
async def testemit_thoughts_puts_multiple_events() -> None:
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    await emit_thoughts(queue, ["thought-A", "thought-B"])

    events = _drain_queue(queue)
    assert len(events) == 2
    assert events[0]["type"] == "planning_thought"
    data0 = cast("JSONObject", events[0]["data"])
    data1 = cast("JSONObject", events[1]["data"])
    assert data0["thought"] == "thought-A"
    assert data1["thought"] == "thought-B"


@pytest.mark.asyncio
async def testemit_thoughts_no_events_for_empty_list() -> None:
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    await emit_thoughts(queue, [])

    assert queue.empty()


@pytest.mark.asyncio
async def test_emit_phase_status_records_metrics_and_logs() -> None:
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    tracker = PhaseTimingTracker()
    tracker.start("planning")
    snapshot = tracker.snapshot("planning", "awaiting_approval")

    with (
        patch(
            "pathfinder.services.chat.streaming.turn_lifecycle.pipeline_phase_events"
        ) as mock_events,
        patch(
            "pathfinder.services.chat.streaming.turn_lifecycle.phase_duration_s"
        ) as mock_duration,
        patch("pathfinder.services.chat.streaming.turn_lifecycle.logger") as mock_logger,
    ):
        await _emit_phase_status(
            queue,
            phase_ctx=PhaseEventContext(
                intent=Intent.NEW_STRATEGY,
                model_id="mock/deterministic",
                run_kind="chat",
            ),
            snapshot=snapshot,
            message_id="phase-msg",
            message_group_id="group-1",
        )

    events = _drain_queue(queue)
    assert len(events) == 1
    assert events[0]["type"] == "phase_change"
    data = cast("JSONObject", events[0]["data"])
    assert data["phase"] == "planning"
    assert data["status"] == "awaiting_approval"
    assert isinstance(data["durationMs"], int)
    assert isinstance(data["phaseStartedAt"], str)
    assert isinstance(data["phaseCompletedAt"], str)

    expected_attrs = {
        "phase": "planning",
        "status": "awaiting_approval",
        "intent": "new_strategy",
        "model": "mock/deterministic",
        "run_kind": "chat",
        "surface": "chat",
    }
    mock_events.add.assert_called_once_with(1, expected_attrs)
    mock_duration.record.assert_called_once_with(
        snapshot.duration_ms / 1000,
        expected_attrs,
    )
    mock_logger.info.assert_called_once()


def test_set_phase_span_attributes_enriches_langfuse_metadata() -> None:
    span = MagicMock()
    deps = SimpleNamespace(
        site_id="plasmodb",
        user_id="user-1",
        context_summary=None,
        problem_frame=object(),
        approved_plan=None,
        plan_action=None,
        turn_metadata={},
        agent_state=SimpleNamespace(active_plan=None),
        strategy_session=SimpleNamespace(
            get_graph=lambda _graph_id: SimpleNamespace(
                id="graph-123",
                name="Transporters",
                record_type="gene",
            )
        ),
    )
    prompt_bundle = PromptBundle(
        text="system text",
        prompts=(
            LoadedPrompt(
                name="system",
                text="system prompt",
                label="production",
                source="langfuse",
                version=3,
            ),
            LoadedPrompt(
                name="safety",
                text="safety prompt",
                label="production",
                source="local",
            ),
        ),
    )

    stream_token = stream_id_ctx.set("stream-1")
    operation_token = operation_id_ctx.set("op_123")
    try:
        with (
            patch(
                "pathfinder.services.chat.streaming.turn_trace_context.get_observability_identity",
                return_value={
                    "service.name": "pathfinder-api",
                    "service.version": "1.2.3",
                    "deployment.environment.name": "development",
                },
            ),
            patch(
                "pathfinder.services.chat.streaming.turn_trace_context.annotate_span_with_observability_identity"
            ),
        ):
            _set_phase_span_attributes(
                span,
                deps,
                span_ctx=PhaseSpanContext(
                    phase="scoping",
                    event=PhaseEventContext(
                        intent=Intent.NEW_STRATEGY,
                        model_id="openai/gpt-4.1-mini",
                        run_kind="chat",
                    ),
                    message_group_id="group-1",
                ),
                phase_input={"prompt": "find genes"},
                prompt_bundle=prompt_bundle,
            )
    finally:
        stream_id_ctx.reset(stream_token)
        operation_id_ctx.reset(operation_token)

    expected_calls = [
        ("langfuse.observation.type", "agent"),
        ("user.id", "user-1"),
        ("session.id", "stream-1"),
        ("langfuse.trace.tags", ["plasmodb", "new_strategy", "chat", "chat"]),
        ("langfuse.trace.metadata.turn_id", "op_123"),
        ("langfuse.trace.metadata.message_group_id", "group-1"),
        ("langfuse.observation.metadata.prompt_bundle", "system@3,safety@local"),
        (
            "langfuse.observation.metadata.prompt_bundle_hash",
            sha256(prompt_bundle.text.encode("utf-8")).hexdigest(),
        ),
        ("langfuse.observation.metadata.run_kind", "chat"),
        ("langfuse.observation.input", '{"prompt":"find genes"}'),
        ("gen_ai.conversation.id", "graph-123"),
    ]
    actual_calls = [call.args for call in span.set_attribute.call_args_list]
    for expected in expected_calls:
        assert expected in actual_calls


def test_turn_trace_metadata_includes_structured_chat_metadata() -> None:
    deps = SimpleNamespace(
        site_id="plasmodb",
        turn_metadata={
            "regenerateOfTraceId": "trace_123",
            "regenerateOfMessageId": "msg_456",
        },
        plan_action=None,
        agent_state=SimpleNamespace(active_plan=None),
        strategy_session=SimpleNamespace(get_graph=lambda _graph_id: None),
    )

    stream_token = stream_id_ctx.set("stream-1")
    operation_token = operation_id_ctx.set("op_123")
    try:
        metadata = _turn_trace_metadata(
            deps,
            intent=Intent.NEW_STRATEGY,
            run_kind="chat",
            message_group_id="group-1",
        )
    finally:
        stream_id_ctx.reset(stream_token)
        operation_id_ctx.reset(operation_token)

    assert metadata["turn_metadata"] == {
        "regenerateOfTraceId": "trace_123",
        "regenerateOfMessageId": "msg_456",
    }
    assert metadata["turn_metadata_keys"] == [
        "regenerateOfMessageId",
        "regenerateOfTraceId",
    ]
    assert metadata["regenerate_of_trace_id"] == "trace_123"
    assert metadata["regenerate_of_message_id"] == "msg_456"
    assert metadata["turn_id"] == "op_123"
    assert metadata["message_group_id"] == "group-1"


@pytest.mark.asyncio
async def test_finalize_stream_logs_turn_summary_and_records_turn_duration() -> None:
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    deps = SimpleNamespace(
        site_id="plasmodb",
        context_summary=None,
        problem_frame=None,
        approved_plan=None,
        plan_action=None,
        agent_state=SimpleNamespace(active_plan=None, discovered_searches={}),
        scoping_result=None,
        discovery_result=None,
        planning_result=None,
        execution_result=None,
        verification_result=None,
    )
    counters = TurnCounters(
        input_tokens=120,
        output_tokens=45,
        cache_read_tokens=12,
        tool_call_count=3,
        llm_call_count=2,
        last_assistant_message="Final answer",
        first_assistant_delta_at_monotonic=8.4,
        first_assistant_message_at_monotonic=9.2,
        first_tool_call_at_monotonic=9.7,
    )
    tracker = PhaseTimingTracker()
    tracker.start("planning")
    tracker.snapshot("planning", "awaiting_approval")
    runtime = TurnRuntimeTelemetry(approval_wait_ms=5000, resume_after_approval_ms=250)
    runtime.record_recovery(
        phase="planning",
        kind="missing_finish",
        summary="Recovered missing finish tool",
    )
    mock_span = MagicMock()
    mock_span.is_recording.return_value = True

    with (
        patch("pathfinder.services.chat.streaming.turn_lifecycle.pipeline_runs") as mock_runs,
        patch(
            "pathfinder.services.chat.streaming.turn_lifecycle.pipeline_turn_duration_s"
        ) as mock_turn_duration,
        patch("pathfinder.services.chat.streaming.turn_lifecycle.token_usage") as mock_tokens,
        patch(
            "pathfinder.services.chat.streaming.turn_lifecycle.pipeline_time_to_first_assistant_delta_s"
        ) as mock_ttfd,
        patch(
            "pathfinder.services.chat.streaming.turn_lifecycle.pipeline_time_to_first_assistant_message_s"
        ) as mock_ttfm,
        patch(
            "pathfinder.services.chat.streaming.turn_lifecycle.pipeline_time_to_first_tool_call_s"
        ) as mock_ttft,
        patch(
            "pathfinder.services.chat.streaming.turn_lifecycle.pipeline_approval_wait_s"
        ) as mock_approval_wait,
        patch(
            "pathfinder.services.chat.streaming.turn_lifecycle.pipeline_resume_after_approval_s"
        ) as mock_resume_after_approval,
        patch(
            "pathfinder.services.chat.streaming.turn_lifecycle.pipeline_execution_duration_s"
        ) as mock_execution_duration,
        patch(
            "pathfinder.services.chat.streaming.turn_lifecycle.pipeline_recoveries"
        ) as mock_recoveries,
        patch("pathfinder.services.chat.streaming.turn_lifecycle.logger") as mock_logger,
        patch(
            "pathfinder.services.chat.streaming.turn_lifecycle.time.monotonic",
            return_value=10.5,
        ),
        patch(
            "pathfinder.services.chat.streaming.turn_lifecycle.trace.get_current_span",
            return_value=mock_span,
        ),
        patch.object(
            runtime,
            "latency_summary",
            return_value=TurnLatencySummary(
                time_to_first_assistant_delta_ms=400,
                time_to_first_assistant_message_ms=1200,
                time_to_first_tool_call_ms=1700,
                approval_wait_ms=5000,
                resume_after_approval_ms=250,
                execution_duration_ms=9000,
            ),
        ),
    ):
        await _finalize_stream(
            queue,
            TurnTelemetryContext(
                deps=deps,
                intent=Intent.NEW_STRATEGY,
                model_id="mock/deterministic",
                run_kind="chat",
                phase_timings=tracker,
                turn_started_at=datetime.now(UTC),
                turn_started_monotonic=8.0,
                runtime=runtime,
            ),
            "completed",
            counters,
            None,
        )

    expected_attrs = {
        "intent": "new_strategy",
        "outcome": "completed",
        "model": "mock/deterministic",
        "run_kind": "chat",
        "surface": "chat",
    }
    mock_runs.add.assert_called_once_with(1, expected_attrs)
    mock_turn_duration.record.assert_called_once_with(2.5, expected_attrs)
    assert mock_tokens.add.call_count == 3
    mock_ttfd.record.assert_called_once_with(0.4, expected_attrs)
    mock_ttfm.record.assert_called_once_with(1.2, expected_attrs)
    mock_ttft.record.assert_called_once_with(1.7, expected_attrs)
    mock_approval_wait.record.assert_called_once_with(5.0, expected_attrs)
    mock_resume_after_approval.record.assert_called_once_with(0.25, expected_attrs)
    mock_execution_duration.record.assert_called_once_with(9.0, expected_attrs)
    mock_recoveries.add.assert_called_once_with(
        1,
        {
            **expected_attrs,
            "phase": "planning",
            "kind": "missing_finish",
        },
    )
    assert mock_tokens.add.call_args_list[0].args == (
        120,
        {
            "model": "mock/deterministic",
            "type": "input",
            "intent": "new_strategy",
            "run_kind": "chat",
            "surface": "chat",
        },
    )
    assert mock_tokens.add.call_args_list[1].args == (
        45,
        {
            "model": "mock/deterministic",
            "type": "output",
            "intent": "new_strategy",
            "run_kind": "chat",
            "surface": "chat",
        },
    )
    assert mock_tokens.add.call_args_list[2].args == (
        12,
        {
            "model": "mock/deterministic",
            "type": "cached",
            "intent": "new_strategy",
            "run_kind": "chat",
            "surface": "chat",
        },
    )
    mock_logger.info.assert_called()
    trace_output_call = next(
        call.args[1]
        for call in mock_span.set_attribute.call_args_list
        if call.args[0] == "langfuse.trace.output"
    )
    trace_output = json.loads(trace_output_call)
    assert trace_output["assistantMessage"] == "Final answer"
    assert trace_output["outcome"] == "completed"
    assert trace_output["latency"]["timeToFirstAssistantDeltaMs"] == 400
    assert trace_output["latency"]["timeToFirstAssistantMessageMs"] == 1200
    assert trace_output["latency"]["timeToFirstToolCallMs"] == 1700
    assert ("app.pipeline.total_duration_ms", 2500) in [
        call.args for call in mock_span.set_attribute.call_args_list
    ]
    assert ("app.pipeline.approval_wait_ms", 5000) in [
        call.args for call in mock_span.set_attribute.call_args_list
    ]
    assert ("app.pipeline.recovery_count", 1) in [
        call.args for call in mock_span.set_attribute.call_args_list
    ]


@pytest.mark.asyncio
async def test_handle_pipeline_error_records_filterable_metric_attrs() -> None:
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    error = RuntimeError("boom")

    with (
        patch("pathfinder.services.chat.streaming.turn_lifecycle.pipeline_errors") as mock_errors,
        patch("pathfinder.services.chat.streaming.turn_lifecycle.trace.get_current_span") as mock_span,
    ):
        span = MagicMock()
        span.is_recording.return_value = False
        mock_span.return_value = span
        await _handle_pipeline_error(
            queue,
            error,
            failure_context=TurnFailureContext(
                error_type="RuntimeError",
                phase="discovery",
                intent="new_strategy",
                run_kind="plan_approval",
            ),
            intent="new_strategy",
            model_id="openai/gpt-4.1",
            run_kind="plan_approval",
        )

    mock_errors.add.assert_called_once_with(
        1,
        {
            "error_type": "RuntimeError",
            "phase": "discovery",
            "intent": "new_strategy",
            "model": "openai/gpt-4.1",
            "run_kind": "plan_approval",
            "surface": "plan_action",
        },
    )
    events = _drain_queue(queue)
    assert len(events) == 1
    assert events[0]["type"] == "error"


@pytest.mark.asyncio
async def test_handle_text_part_start_emits_initial_assistant_delta() -> None:
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    counters = TurnCounters()
    event = PartStartEvent(index=0, part=TextPart(content="Hello world"))
    stripper = StreamingTagStripper()

    await handle_text_part_start(
        event,
        stripper,
        queue,
        StreamMessageContext(
            message_id="msg-1",
            message_group_id="group-1",
            phase="execution",
        ),
        counters,
    )

    events = _drain_queue(queue)
    assert len(events) == 1
    assert events[0]["type"] == "assistant_delta"
    data = cast("JSONObject", events[0]["data"])
    assert data["delta"] == "Hello world"
    assert data["messageId"] == "msg-1"
    assert data["messageGroupId"] == "group-1"
    assert data["phase"] == "execution"
    assert counters.saw_assistant_message is True
    assert counters.first_assistant_delta_at_monotonic is not None


@pytest.mark.asyncio
async def test_stream_call_tools_marks_valid_finish_scoping_as_phase_exit() -> None:
    deps = _make_deps()
    deps.problem_frame = ProblemFrame(
        user_goal="Find transporters",
        interpreted_goal="Identify transporter genes",
        organism_scope="P. vivax",
        record_type="gene",
        ready_for_wdk_discovery=True,
        confidence=0.9,
    )
    deps.scoping_result = ScopingResult(problem_frame=deps.problem_frame)
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    counters = TurnCounters()
    call = ToolCallPart(
        tool_name="finish_scoping",
        args='{"decision":"continue_to_discovery","summary":"Scoped."}',
        tool_call_id="tool-1",
    )
    result = ToolReturnPart(
        tool_name="finish_scoping",
        tool_call_id="tool-1",
        content='{"phaseDecision":{"phase":"scoping","decision":"continue_to_discovery","summary":"Scoped.","questions":[]}}',
    )
    deps.scoping_result = ScopingResult(
        problem_frame=deps.problem_frame,
        decision=PhaseDecision(
            phase="scoping",
            decision="continue_to_discovery",
            summary="Scoped.",
        ),
    )

    should_terminate = await stream_call_tools(
        _FakeCallToolsNode(
            [
                FunctionToolCallEvent(part=call),
                FunctionToolResultEvent(result=result),
            ]
        ),
        SimpleNamespace(ctx=object()),
        queue,
        deps,
        counters,
    )

    assert should_terminate is True
    events = _drain_queue(queue)
    assert [event["type"] for event in events] == ["tool_call_start", "tool_call_end"]


@pytest.mark.asyncio
async def test_stream_call_tools_does_not_terminate_on_invalid_finish_scoping() -> None:
    deps = _make_deps()
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    call = ToolCallPart(
        tool_name="finish_scoping",
        args='{"decision":"continue_to_discovery","summary":"Scoped."}',
        tool_call_id="tool-2",
    )
    result = ToolReturnPart(
        tool_name="finish_scoping",
        tool_call_id="tool-2",
        content='{"code":"MISSING_PROBLEM_FRAME","message":"Call set_problem_frame before finish_scoping."}',
    )

    should_terminate = await stream_call_tools(
        _FakeCallToolsNode(
            [
                FunctionToolCallEvent(part=call),
                FunctionToolResultEvent(result=result),
            ]
        ),
        SimpleNamespace(ctx=object()),
        queue,
        deps,
        TurnCounters(),
    )

    assert should_terminate is False


@pytest.mark.asyncio
async def test_run_phase_inner_stops_after_phase_exit_tool_node() -> None:
    deps = _make_deps()
    config = PhaseConfig(
        phase="scoping",
        prompt="find transporters",
        deps=deps,
        queue=asyncio.Queue(),
        message_id="msg-1",
        counters=TurnCounters(),
        message_group_id="group-1",
        model_id="mock/deterministic",
        reasoning_effort="low",
    )
    call_node = object()
    later_model_node = object()
    fake_run = _FakeRun([call_node, later_model_node])
    fake_agent = _FakeAgent(fake_run)

    with (
        patch(
            "pathfinder.services.chat.streaming.phase_runner.Agent.is_call_tools_node",
            side_effect=lambda node: node is call_node,
        ),
        patch(
            "pathfinder.services.chat.streaming.phase_runner.Agent.is_model_request_node",
            side_effect=lambda node: node is later_model_node,
        ),
        patch(
            "pathfinder.services.chat.streaming.phase_runner.stream_call_tools",
            new=AsyncMock(return_value=True),
        ) as mock_stream_call_tools,
        patch(
            "pathfinder.services.chat.streaming.phase_runner.stream_model_request",
            new=AsyncMock(),
        ) as mock_stream_model_request,
    ):
        phase_messages = await _run_phase_inner(config, fake_agent)

    mock_stream_call_tools.assert_awaited_once()
    mock_stream_model_request.assert_not_awaited()
    assert phase_messages == []


# ── merge_usage ──────────────────────────────────────────────────────────


def testmerge_usage_accumulates_tokens() -> None:
    """merge_usage should fold Usage into running counters."""
    counters = TurnCounters()
    usage1 = RunUsage(input_tokens=100, output_tokens=50, cache_read_tokens=10, requests=1)
    usage2 = RunUsage(input_tokens=200, output_tokens=75, cache_read_tokens=20, requests=2)

    merge_usage(counters, usage1)
    merge_usage(counters, usage2)

    assert counters.input_tokens == 300
    assert counters.output_tokens == 125
    assert counters.cache_read_tokens == 30
    assert counters.llm_call_count == 3


def testmerge_usage_handles_none_tokens() -> None:
    counters = TurnCounters()
    usage = RunUsage()  # All None

    merge_usage(counters, usage)

    assert counters.input_tokens == 0
    assert counters.output_tokens == 0
    assert counters.cache_read_tokens == 0


# ── parse_tool_call_args ──────────────────────────────────────────────────


def testparse_tool_call_args_dict() -> None:
    result = parse_tool_call_args({"key": "value"})
    assert result == {"key": "value"}


def testparse_tool_call_args_json_string() -> None:
    result = parse_tool_call_args('{"a": 1}')
    assert result == {"a": 1}


def testparse_tool_call_args_invalid_json_string() -> None:
    result = parse_tool_call_args("not json")
    assert result == {}


def testparse_tool_call_args_json_array_string_returns_empty() -> None:
    """A JSON array string should return an empty dict, not the array."""
    result = parse_tool_call_args("[1, 2, 3]")
    assert result == {}


def testparse_tool_call_args_none() -> None:
    result = parse_tool_call_args(None)
    assert result == {}


# ── StreamingTagStripper edge cases ──────────────────────────────────────


def test_tag_stripper_only_whitespace_inside_tag() -> None:
    """Whitespace-only content inside a tag should not produce a thought."""
    stripper = StreamingTagStripper()

    clean, thoughts = stripper.feed("<plan-thinking>   \n  </plan-thinking>ok")
    remaining = stripper.flush()

    assert thoughts == []
    assert "ok" in (clean + remaining)


def test_tag_stripper_reset_state_on_flush() -> None:
    """After flush, the stripper should be in a clean initial state."""
    stripper = StreamingTagStripper()

    stripper.feed("<plan-thinking>thinking")
    stripper.flush()

    # After flush, _inside_tag should be False and buffer empty
    assert stripper._buffer == ""
    assert stripper._inside_tag is False

    # New feed should work without leftover state
    clean, thoughts = stripper.feed("fresh text")
    remaining2 = stripper.flush()
    assert (clean + remaining2) == "fresh text"
    assert thoughts == []


def test_tag_stripper_special_characters_in_thought() -> None:
    """Thought content with special characters (quotes, angles, newlines)."""
    stripper = StreamingTagStripper()

    content = '<plan-thinking>Look at <gene> "PF3D7_0100100" & analyze\nit</plan-thinking>'
    _clean, thoughts = stripper.feed(content)
    stripper.flush()

    assert len(thoughts) == 1
    assert '"PF3D7_0100100"' in thoughts[0]
    assert "& analyze" in thoughts[0]


# ── TurnCounters ─────────────────────────────────────────────────────────


def test_turn_counters_initial_state() -> None:
    counters = TurnCounters()

    assert counters.saw_assistant_message is False
    assert counters.input_tokens == 0
    assert counters.output_tokens == 0
    assert counters.cache_read_tokens == 0
    assert counters.tool_call_count == 0
    assert counters.llm_call_count == 0
    assert counters.accumulated_text_parts == []
    assert counters.last_assistant_message is None
    assert counters.first_assistant_delta_at_monotonic is None
    assert counters.first_assistant_message_at_monotonic is None
    assert counters.first_tool_call_at_monotonic is None


def test_turn_counters_accumulated_text_parts() -> None:
    counters = TurnCounters()

    counters.accumulated_text_parts.append("Part 1")
    counters.accumulated_text_parts.append("Part 2")

    assert len(counters.accumulated_text_parts) == 2
    assert "\n\n".join(counters.accumulated_text_parts) == "Part 1\n\nPart 2"
