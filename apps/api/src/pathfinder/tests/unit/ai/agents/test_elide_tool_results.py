"""Tests for :func:`elide_consumed_tool_results`.

The processor must:
1. Replace ``ToolReturnPart.content`` for *older* tool returns with a stub.
2. Leave the most-recent ``KEEP_RECENT_TOOL_PAIRS`` returns untouched.
3. Preserve every ``ToolCallPart`` and ``ToolReturnPart.tool_call_id`` so
   the provider doesn't reject the request as orphaned (Anthropic and
   OpenAI both reject calls without matching returns and vice versa).
4. Not mutate non-tool parts (system prompts, user prompts, text).

These are the contractual properties — if any of them break, the next
LLM request will either be billed for the bloat we tried to elide, or
fail outright with a "tool_use_id has no matching tool_result" error.
"""
from __future__ import annotations

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from pathfinder.ai.agents._history_processor import (
    KEEP_RECENT_TOOL_PAIRS,
    elide_consumed_tool_results,
)


def _user(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def _system(text: str) -> ModelRequest:
    return ModelRequest(parts=[SystemPromptPart(content=text)])


def _call(call_id: str, name: str = "tool_x") -> ToolCallPart:
    return ToolCallPart(tool_name=name, args={}, tool_call_id=call_id)


def _assistant_with_call(call_id: str, name: str = "tool_x") -> ModelResponse:
    return ModelResponse(parts=[_call(call_id, name)])


def _assistant_text(text: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content=text)])


def _tool_return(
    call_id: str,
    content: str = "BIG_RESULT_PAYLOAD",
    name: str = "tool_x",
) -> ModelRequest:
    return ModelRequest(
        parts=[
            ToolReturnPart(
                tool_name=name, content=content, tool_call_id=call_id,
            ),
        ],
    )


def _interleaved_tool_calls(
    n: int,
    *,
    return_content: str = "BIG_RESULT_PAYLOAD",
) -> list[ModelMessage]:
    """User prompt followed by ``n`` assistant→toolReturn round-trips."""
    out: list[ModelMessage] = [_user("kick off")]
    for i in range(n):
        out.append(_assistant_with_call(f"call_{i}"))
        out.append(_tool_return(f"call_{i}", content=return_content))
    return out


def _returns_in_order(
    messages: list[ModelMessage],
) -> list[ToolReturnPart]:
    out: list[ToolReturnPart] = []
    for msg in messages:
        if not isinstance(msg, ModelRequest):
            continue
        out.extend(p for p in msg.parts if isinstance(p, ToolReturnPart))
    return out


def _calls_in_order(messages: list[ModelMessage]) -> list[ToolCallPart]:
    out: list[ToolCallPart] = []
    for msg in messages:
        if not isinstance(msg, ModelResponse):
            continue
        out.extend(p for p in msg.parts if isinstance(p, ToolCallPart))
    return out


# ---------------------------------------------------------------------------
# Empty / under-threshold cases — processor must be a no-op
# ---------------------------------------------------------------------------


def test_no_tool_calls_at_all() -> None:
    """Pure text exchange: nothing to elide. Output identical to input."""
    msgs: list[ModelMessage] = [
        _system("you are an assistant"),
        _user("hello"),
        _assistant_text("hi"),
    ]
    out = elide_consumed_tool_results(list(msgs))
    assert out == msgs


def test_under_keep_threshold_is_no_op() -> None:
    """When tool-call count <= KEEP_RECENT_TOOL_PAIRS, every return body
    must survive intact — none have been "consumed" yet."""
    msgs = _interleaved_tool_calls(KEEP_RECENT_TOOL_PAIRS)
    out = elide_consumed_tool_results(list(msgs))
    for ret in _returns_in_order(out):
        assert ret.content == "BIG_RESULT_PAYLOAD"


def test_exactly_at_keep_threshold_is_no_op() -> None:
    msgs = _interleaved_tool_calls(KEEP_RECENT_TOOL_PAIRS)
    out = elide_consumed_tool_results(list(msgs))
    assert out == msgs


# ---------------------------------------------------------------------------
# The core elision contract
# ---------------------------------------------------------------------------


def test_older_returns_get_stub_recent_returns_keep_payload() -> None:
    """The defining behaviour: with N tool calls where N > K, the first
    N-K return bodies are replaced with the stub; the last K survive."""
    n = KEEP_RECENT_TOOL_PAIRS + 5
    msgs = _interleaved_tool_calls(n)
    out = elide_consumed_tool_results(list(msgs))
    returns = _returns_in_order(out)
    assert len(returns) == n
    elided_count = n - KEEP_RECENT_TOOL_PAIRS
    elided = returns[:elided_count]
    kept = returns[elided_count:]
    assert all(r.content != "BIG_RESULT_PAYLOAD" for r in elided)
    assert all("elided" in str(r.content).lower() for r in elided)
    assert all(r.content == "BIG_RESULT_PAYLOAD" for r in kept)
    assert len(kept) == KEEP_RECENT_TOOL_PAIRS


def test_pairing_is_preserved() -> None:
    """Provider-rejection guard: every ToolCallPart must still have a
    matching ToolReturnPart with the same tool_call_id afterwards. The
    elision changes the result *body*, never the wiring."""
    n = KEEP_RECENT_TOOL_PAIRS + 7
    msgs = _interleaved_tool_calls(n)
    out = elide_consumed_tool_results(list(msgs))
    call_ids = [c.tool_call_id for c in _calls_in_order(out)]
    return_ids = [r.tool_call_id for r in _returns_in_order(out)]
    assert call_ids == [f"call_{i}" for i in range(n)]
    assert return_ids == call_ids


def test_tool_call_args_are_not_touched() -> None:
    """We elide *result* bodies, not call arguments. The model's own
    output (the call args) is small and stays for context — only the
    bulky tool result payload gets the stub."""
    msgs: list[ModelMessage] = [_user("go")]
    for i in range(KEEP_RECENT_TOOL_PAIRS + 3):
        call = ToolCallPart(
            tool_name="search",
            args={"q": f"query_{i}", "context": "important_args"},
            tool_call_id=f"call_{i}",
        )
        msgs.append(ModelResponse(parts=[call]))
        msgs.append(_tool_return(f"call_{i}", content="HUGE_RESPONSE"))
    out = elide_consumed_tool_results(list(msgs))
    for call in _calls_in_order(out):
        assert call.args == {
            "q": call.args["q"]
            if isinstance(call.args, dict) else "query_x",
            "context": "important_args",
        } or isinstance(call.args, str)


def test_user_and_system_messages_untouched() -> None:
    """Elision must never touch SystemPromptPart / UserPromptPart — those
    aren't tool results and the agent's framing depends on them."""
    msgs: list[ModelMessage] = [
        _system("scoped to PathFinder"),
        _user("find Plasmodium kinases"),
    ]
    msgs.extend(_interleaved_tool_calls(KEEP_RECENT_TOOL_PAIRS + 2)[1:])
    msgs.append(_user("follow-up question"))
    out = elide_consumed_tool_results(list(msgs))
    sys_prompts: list[SystemPromptPart] = []
    user_prompts: list[UserPromptPart] = []
    for msg in out:
        if isinstance(msg, ModelRequest):
            sys_prompts.extend(
                p for p in msg.parts if isinstance(p, SystemPromptPart)
            )
            user_prompts.extend(
                p for p in msg.parts if isinstance(p, UserPromptPart)
            )
    assert [p.content for p in sys_prompts] == ["scoped to PathFinder"]
    user_contents = [p.content for p in user_prompts]
    assert "find Plasmodium kinases" in user_contents
    assert "follow-up question" in user_contents


def test_retry_prompt_parts_untouched() -> None:
    """RetryPromptPart carries error feedback the model needs verbatim
    — never elide those."""
    retry = RetryPromptPart(
        content="invalid arguments — try again",
        tool_call_id="call_0",
        tool_name="tool_x",
    )
    msgs: list[ModelMessage] = [_user("go")]
    for i in range(KEEP_RECENT_TOOL_PAIRS + 2):
        msgs.append(_assistant_with_call(f"call_{i}"))
        msgs.append(
            ModelRequest(
                parts=[
                    retry if i == 0 else ToolReturnPart(
                        tool_name="tool_x",
                        content="OK",
                        tool_call_id=f"call_{i}",
                    ),
                ],
            ),
        )
    out = elide_consumed_tool_results(list(msgs))
    found_retry = False
    for msg in out:
        if not isinstance(msg, ModelRequest):
            continue
        for part in msg.parts:
            if isinstance(part, RetryPromptPart):
                assert part.content == "invalid arguments — try again"
                found_retry = True
    assert found_retry


# ---------------------------------------------------------------------------
# Idempotency + composition with pair_tool_calls
# ---------------------------------------------------------------------------


def test_idempotent_when_already_elided() -> None:
    """Running the processor twice must not double-elide or otherwise
    mutate. ``before_model_request`` fires before *every* LLM call, so
    when the agent makes 30 model requests the same history may pass
    through the processor 30 times. Successive runs must be no-ops."""
    msgs = _interleaved_tool_calls(KEEP_RECENT_TOOL_PAIRS + 4)
    once = elide_consumed_tool_results(list(msgs))
    twice = elide_consumed_tool_results(once)
    assert once == twice


def test_text_only_assistant_responses_not_dropped() -> None:
    """Assistant ``TextPart`` content (model prose) must pass through
    unchanged — only ``ToolReturnPart`` content gets elided."""
    msgs: list[ModelMessage] = [_user("go")]
    for i in range(KEEP_RECENT_TOOL_PAIRS + 1):
        msgs.append(
            ModelResponse(
                parts=[
                    TextPart(content=f"thinking step {i}"),
                    _call(f"call_{i}"),
                ],
            ),
        )
        msgs.append(_tool_return(f"call_{i}"))
    out = elide_consumed_tool_results(list(msgs))
    text_contents: list[str] = []
    for msg in out:
        if not isinstance(msg, ModelResponse):
            continue
        text_contents.extend(
            p.content for p in msg.parts if isinstance(p, TextPart)
        )
    expected = [
        f"thinking step {i}" for i in range(KEEP_RECENT_TOOL_PAIRS + 1)
    ]
    assert text_contents == expected


# ---------------------------------------------------------------------------
# Realistic discovery-phase shape (the actual cause of the 1.94M-token bug)
# ---------------------------------------------------------------------------


def test_realistic_30_call_discovery_loop_collapses_payload() -> None:
    """The exact shape that caused turn-2's 1.94M-token blowup: a
    discovery loop with ~30 search/parameter inspections. Each tool
    return is ~3KB. After elision, only the last K returns carry the
    full payload — the rest collapse to the stub. Asserts on bytes
    saved so a regression here would visibly bring the bug back."""
    big = "X" * 3000  # 3KB synthetic tool result
    n = 30
    msgs = _interleaved_tool_calls(n, return_content=big)
    out = elide_consumed_tool_results(list(msgs))
    returns = _returns_in_order(out)
    full_count = sum(1 for r in returns if r.content == big)
    assert full_count == KEEP_RECENT_TOOL_PAIRS
    elided_bytes = sum(
        len(big) - len(str(r.content))
        for r in returns
        if r.content != big
    )
    # Sanity: we save (n - K) * (~3KB - stub_size) ≈ tens of KB per request.
    assert elided_bytes > 50_000
