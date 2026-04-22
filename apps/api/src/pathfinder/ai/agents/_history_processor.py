"""Pair orphan tool_calls/returns in message history before each model request."""
from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)

from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

_PLACEHOLDER_CONTENT = (
    "Tool call was not executed (prior stream error). Treat as failed and "
    "proceed without the expected result."
)


def _collect_ids(
    messages: Sequence[ModelMessage],
) -> tuple[set[str], set[str], bool]:
    """Return ``(call_ids, satisfied_ids, has_duplicate_returns)``.

    A tool call is *satisfied* by either a ``ToolReturnPart`` (normal
    result) or a ``RetryPromptPart`` carrying the same ``tool_call_id``.
    When a tool raises ``ModelRetry``, pydantic-ai adds a ``RetryPromptPart``
    (no ``ToolReturnPart``) — the call is not orphan.
    """
    call_ids: set[str] = set()
    satisfied_ids: set[str] = set()
    seen_returns: set[str] = set()
    has_duplicates = False
    for msg in messages:
        for part in msg.parts:
            if isinstance(part, ToolCallPart):
                call_ids.add(part.tool_call_id)
            elif isinstance(part, ToolReturnPart):
                satisfied_ids.add(part.tool_call_id)
                if part.tool_call_id in seen_returns:
                    has_duplicates = True
                seen_returns.add(part.tool_call_id)
            elif isinstance(part, RetryPromptPart) and part.tool_call_id:
                satisfied_ids.add(part.tool_call_id)
    return call_ids, satisfied_ids, has_duplicates


def _drop_orphan_and_duplicate_returns(
    messages: Sequence[ModelMessage],
    orphan_return_ids: set[str],
) -> list[ModelMessage]:
    """Remove tool returns that have no matching call AND dedupe returns.

    Anthropic's API rejects multiple ``tool_result`` blocks for the same
    ``tool_use_id``; OpenAI silently tolerates them but downstream logic
    breaks. Keep the FIRST occurrence of each tool_call_id and drop later
    duplicates.
    """
    seen_return_ids: set[str] = set()
    cleaned: list[ModelMessage] = []
    for msg in messages:
        if not isinstance(msg, ModelRequest):
            cleaned.append(msg)
            continue
        kept_parts: list[object] = []
        for p in msg.parts:
            if isinstance(p, ToolReturnPart):
                if p.tool_call_id in orphan_return_ids:
                    continue
                if p.tool_call_id in seen_return_ids:
                    continue
                seen_return_ids.add(p.tool_call_id)
            kept_parts.append(p)
        if not kept_parts:
            continue
        if len(kept_parts) == len(msg.parts):
            cleaned.append(msg)
        else:
            cleaned.append(dataclasses.replace(msg, parts=list(kept_parts)))
    return cleaned


def _find_orphan_call_locations(
    messages: Sequence[ModelMessage],
    orphan_call_ids: set[str],
) -> dict[int, list[ToolCallPart]]:
    locations: dict[int, list[ToolCallPart]] = {}
    for idx, msg in enumerate(messages):
        if not isinstance(msg, ModelResponse):
            continue
        orphans = [
            p
            for p in msg.parts
            if isinstance(p, ToolCallPart) and p.tool_call_id in orphan_call_ids
        ]
        if orphans:
            locations[idx] = orphans
    return locations


def _placeholder_return(call: ToolCallPart) -> ToolReturnPart:
    return ToolReturnPart(
        tool_name=call.tool_name,
        content=_PLACEHOLDER_CONTENT,
        tool_call_id=call.tool_call_id,
    )


def _inject_placeholder_returns(
    messages: list[ModelMessage],
    orphan_call_ids: set[str],
) -> list[ModelMessage]:
    if not orphan_call_ids:
        return messages

    locations = _find_orphan_call_locations(messages, orphan_call_ids)
    if not locations:
        return messages

    result: list[ModelMessage] = list(messages)
    for response_idx in sorted(locations.keys(), reverse=True):
        placeholders = [_placeholder_return(call) for call in locations[response_idx]]
        next_idx = response_idx + 1
        next_msg = result[next_idx] if next_idx < len(result) else None
        if isinstance(next_msg, ModelRequest):
            result[next_idx] = dataclasses.replace(
                next_msg, parts=list(placeholders) + list(next_msg.parts),
            )
        else:
            result.insert(next_idx, ModelRequest(parts=list(placeholders)))
    return result


def pair_tool_calls(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Return a cleaned copy of ``messages`` with tool-call/return pairing fixed."""
    call_ids, satisfied_ids, has_duplicates = _collect_ids(messages)
    orphan_return_ids = satisfied_ids - call_ids
    orphan_call_ids = call_ids - satisfied_ids

    if not orphan_return_ids and not orphan_call_ids and not has_duplicates:
        return list(messages)

    logger.warning(
        "message_history integrity correction applied",
        orphan_return_ids=sorted(orphan_return_ids),
        orphan_call_ids=sorted(orphan_call_ids),
        has_duplicate_returns=has_duplicates,
        total_messages=len(messages),
    )

    cleaned = _drop_orphan_and_duplicate_returns(messages, orphan_return_ids)
    return _inject_placeholder_returns(cleaned, orphan_call_ids)
