"""Tool-call-safe reducer for ``PipelineState.message_history``.

OpenAI (and most other providers) reject a message history where a ``tool``
role message has no immediately-preceding ``assistant`` message whose
``tool_calls`` array contains its ``tool_call_id``. This is easy to violate
in our pipeline: a phase's stream can error mid-call and return
``new_messages`` that include a ``ToolCallPart`` without a matching
``ToolReturnPart`` (or vice-versa). A raw ``operator.add`` reducer appends
them unchanged and the *next* turn's replay blows up.

``append_messages_safely`` concatenates the two lists and enforces
tool-call integrity before returning:

1. Drop any ``ToolReturnPart`` whose ``tool_call_id`` has no matching
   ``ToolCallPart`` earlier in the combined history.
2. Synthesize a placeholder ``ToolReturnPart`` for every orphan
   ``ToolCallPart`` so the assistant's tool call has a response to pair
   with when replayed. The placeholder is inserted into the next
   ``ModelRequest`` after the orphan call; if no such request exists, a
   new ``ModelRequest`` is appended at the end.

Any correction is logged once with the affected ``tool_call_id`` so we can
trace poisoned histories back to their source turn.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
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
) -> tuple[set[str], set[str]]:
    """Return ``(call_ids, return_ids)`` across all messages."""
    call_ids: set[str] = set()
    return_ids: set[str] = set()
    for msg in messages:
        for part in msg.parts:
            if isinstance(part, ToolCallPart):
                call_ids.add(part.tool_call_id)
            elif isinstance(part, ToolReturnPart):
                return_ids.add(part.tool_call_id)
    return call_ids, return_ids


def _drop_orphan_returns(
    messages: Sequence[ModelMessage],
    orphan_return_ids: set[str],
) -> list[ModelMessage]:
    """Remove ``ToolReturnPart``s whose call-id is unanswered earlier."""
    cleaned: list[ModelMessage] = []
    for msg in messages:
        if not isinstance(msg, ModelRequest):
            cleaned.append(msg)
            continue
        kept_parts = [
            p
            for p in msg.parts
            if not (
                isinstance(p, ToolReturnPart)
                and p.tool_call_id in orphan_return_ids
            )
        ]
        if not kept_parts:
            # Entire ModelRequest consisted of orphan tool returns — drop it.
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
    """Map ``ModelResponse`` index → orphan ``ToolCallPart``s it contains."""
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
    """Insert placeholder ``ToolReturnPart``s for every orphan call.

    Placeholders are *prepended* to the next ``ModelRequest`` after each
    orphan call so the emitted wire sequence preserves the
    ``assistant(tool_calls) → tool`` adjacency OpenAI requires — any
    ``UserPromptPart`` / ``SystemPromptPart`` in the same request must come
    after the placeholder, not before. If there is no following
    ``ModelRequest``, a new one is added to carry the placeholders.
    """
    if not orphan_call_ids:
        return messages

    locations = _find_orphan_call_locations(messages, orphan_call_ids)
    if not locations:
        return messages

    result: list[ModelMessage] = list(messages)
    # Walk orphan responses in reverse so earlier insertions don't invalidate
    # later indices. For each, find the first ModelRequest after it.
    for response_idx in sorted(locations.keys(), reverse=True):
        orphans = locations[response_idx]
        placeholders = [_placeholder_return(call) for call in orphans]
        target_idx: int | None = None
        for j in range(response_idx + 1, len(result)):
            if isinstance(result[j], ModelRequest):
                target_idx = j
                break
        if target_idx is None:
            # No trailing request — synthesize one.
            result.append(ModelRequest(parts=list(placeholders)))
        else:
            target = result[target_idx]
            assert isinstance(target, ModelRequest)  # noqa: S101
            result[target_idx] = dataclasses.replace(
                target,
                parts=list(placeholders) + list(target.parts),
            )
    return result


def append_messages_safely(
    existing: Sequence[ModelMessage], new: Sequence[ModelMessage]
) -> list[ModelMessage]:
    """Append ``new`` to ``existing`` while preserving tool-call/response pairing.

    Used as the reducer for ``PipelineState.message_history``. Logs a warning
    the first time a correction is needed so orphan cases are visible in
    traces without spamming the log on every turn.
    """
    combined: list[ModelMessage] = list(existing) + list(new)

    call_ids, return_ids = _collect_ids(combined)
    orphan_return_ids = return_ids - call_ids
    orphan_call_ids = call_ids - return_ids

    if not orphan_return_ids and not orphan_call_ids:
        return combined

    logger.warning(
        "message_history integrity correction applied",
        orphan_return_ids=sorted(orphan_return_ids),
        orphan_call_ids=sorted(orphan_call_ids),
        total_messages=len(combined),
    )

    cleaned = _drop_orphan_returns(combined, orphan_return_ids)
    return _inject_placeholder_returns(cleaned, orphan_call_ids)
