from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence

from assistant_core.platform.logging import get_logger
from pydantic_ai.messages import (
    BaseToolCallPart,
    BaseToolReturnPart,
    CompactionPart,
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    ModelResponsePart,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

logger = get_logger(__name__)

_PLACEHOLDER_CONTENT = (
    "Tool call was not executed (prior stream error). Treat as failed and "
    "proceed without the expected result."
)

KEEP_RECENT_TOOL_PAIRS = 3

_ELIDE_MIN_CHARS = 400
"""Results at or below this stay whole.

A count or an id costs a few tokens to keep and a whole round trip to
re-fetch, so a small result is worth more in history than out of it.
"""

_ELIDE_DIGEST_CHARS = 220

_ELIDED_MARKER = "<elided to control context size"


def _digest(content: object) -> str:
    """Compress a bulky result, keeping the head so its facts survive.

    A stub with no readable head invites the model to re-fetch the same
    data; a head that keeps counts and ids stays answerable from history.
    """
    try:
        rendered = content if isinstance(content, str) else json.dumps(content)
    except TypeError, ValueError:
        rendered = str(content)
    head = rendered[:_ELIDE_DIGEST_CHARS]
    return f"{head}... {_ELIDED_MARKER}; already acted on, do not fetch again>"


def _already_elided(content: object) -> bool:
    """Idempotent: a digest must not be digested again on the next pass."""
    return isinstance(content, str) and content.endswith(
        "already acted on, do not fetch again>"
    )


def _too_small_to_elide(content: object) -> bool:
    try:
        rendered = content if isinstance(content, str) else json.dumps(content)
    except TypeError, ValueError:
        rendered = str(content)
    return len(rendered) <= _ELIDE_MIN_CHARS


def _collect_ids(
    messages: Sequence[ModelMessage],
) -> tuple[set[str], set[str], bool, bool]:
    # ``ModelRetry`` produces a ``RetryPromptPart`` (no ``ToolReturnPart``)
    # carrying the same ``tool_call_id`` — also counts as satisfying the call.
    call_ids: set[str] = set()
    satisfied_ids: set[str] = set()
    seen_returns: set[str] = set()
    seen_calls: set[str] = set()
    has_duplicate_returns = False
    has_duplicate_calls = False
    for msg in messages:
        for part in msg.parts:
            if isinstance(part, ToolCallPart):
                if part.tool_call_id in seen_calls:
                    has_duplicate_calls = True
                seen_calls.add(part.tool_call_id)
                call_ids.add(part.tool_call_id)
            elif isinstance(part, ToolReturnPart):
                satisfied_ids.add(part.tool_call_id)
                if part.tool_call_id in seen_returns:
                    has_duplicate_returns = True
                seen_returns.add(part.tool_call_id)
            elif isinstance(part, RetryPromptPart) and part.tool_call_id:
                satisfied_ids.add(part.tool_call_id)
    return call_ids, satisfied_ids, has_duplicate_returns, has_duplicate_calls


def _drop_orphan_and_duplicate_returns(
    messages: Sequence[ModelMessage],
    orphan_return_ids: set[str],
) -> list[ModelMessage]:
    # Anthropic rejects multiple ``tool_result`` blocks for the same
    # ``tool_use_id``; keep the first, drop later duplicates.
    seen_return_ids: set[str] = set()
    cleaned: list[ModelMessage] = []
    for msg in messages:
        if not isinstance(msg, ModelRequest):
            cleaned.append(msg)
            continue
        kept_parts: list[ModelRequestPart] = []
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
            cleaned.append(dataclasses.replace(msg, parts=kept_parts))
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
                next_msg,
                parts=list(placeholders) + list(next_msg.parts),
            )
        else:
            result.insert(next_idx, ModelRequest(parts=list(placeholders)))
    return result


def pair_tool_calls(messages: list[ModelMessage]) -> list[ModelMessage]:
    (
        call_ids,
        satisfied_ids,
        has_duplicate_returns,
        has_duplicate_calls,
    ) = _collect_ids(messages)
    orphan_return_ids = satisfied_ids - call_ids
    orphan_call_ids = call_ids - satisfied_ids

    if (
        not orphan_return_ids
        and not orphan_call_ids
        and not has_duplicate_returns
        and not has_duplicate_calls
    ):
        return list(messages)

    logger.error(
        "message_history integrity correction applied",
        orphan_return_ids=sorted(orphan_return_ids),
        orphan_call_ids=sorted(orphan_call_ids),
        has_duplicate_returns=has_duplicate_returns,
        has_duplicate_calls=has_duplicate_calls,
        total_messages=len(messages),
    )

    cleaned = _drop_orphan_and_duplicate_returns(messages, orphan_return_ids)
    return _inject_placeholder_returns(cleaned, orphan_call_ids)


def _ordered_tool_call_ids(messages: Sequence[ModelMessage]) -> list[str]:
    out: list[str] = []
    for msg in messages:
        if not isinstance(msg, ModelResponse):
            continue
        out.extend(
            part.tool_call_id for part in msg.parts if isinstance(part, ToolCallPart)
        )
    return out


def elide_consumed_tool_results(
    messages: list[ModelMessage],
) -> list[ModelMessage]:
    # Replace older ``ToolReturnPart`` bodies with a stub, keeping the most
    # recent ``KEEP_RECENT_TOOL_PAIRS`` intact. Pairing is preserved
    # (Anthropic/OpenAI reject orphans); only result *content* is shortened.
    call_ids = _ordered_tool_call_ids(messages)
    if len(call_ids) <= KEEP_RECENT_TOOL_PAIRS:
        return list(messages)
    elide_ids = set(call_ids[:-KEEP_RECENT_TOOL_PAIRS])
    return [_elide_returns_in_message(msg, elide_ids) for msg in messages]


def _elide_returns_in_message(
    msg: ModelMessage,
    elide_ids: set[str],
) -> ModelMessage:
    if not isinstance(msg, ModelRequest):
        return msg
    new_parts: list[ModelRequestPart] = []
    changed = False
    for part in msg.parts:
        # Mask any consumed return — including structured (Pydantic / list /
        # dict) content. pydantic-ai keeps the raw object in ``.content`` and
        # serializes it only at request-build time, so an ``isinstance(str)``
        # guard here would skip exactly the heavy discovery payloads
        # (search results, parameter schemas, vocabularies) this is meant to
        # compress. ``content != stub`` keeps it idempotent: once replaced,
        # the stub string compares equal and is left alone.
        if (
            isinstance(part, ToolReturnPart)
            and part.tool_call_id in elide_ids
            and not part.files
            and not _already_elided(part.content)
            and not _too_small_to_elide(part.content)
        ):
            new_parts.append(
                dataclasses.replace(part, content=_digest(part.content)),
            )
            changed = True
        else:
            new_parts.append(part)
    if not changed:
        return msg
    return dataclasses.replace(msg, parts=new_parts)


COMPACT_AT_ESTIMATED_TOKENS = 100_000
# The kept tail is sized by what it costs, because a few vocabulary reads can
# outweigh the whole middle. The floor lets a pass act on its latest result
# whatever that result costs.
KEEP_RECENT_EXCHANGE_TOKENS = COMPACT_AT_ESTIMATED_TOKENS // 2
MIN_KEEP_RECENT_EXCHANGES = 2

_DIGEST_CHAR_CAP = 4_000
_DIGEST_OPENING = (
    "Earlier steps were compacted to save context. What happened, oldest first:"
)
_DIGEST_CLOSING = (
    "The workspace state (spec draft, notes) already reflects all of this; "
    "do not redo these calls."
)
_OMITTED_MARKER = "(oldest lines omitted)"
_ARGS_HEAD_CHARS = 80
_RESULT_HEAD_CHARS = 160
_CHARS_PER_TOKEN = 4

_CONTENT_PARTS = (
    SystemPromptPart,
    UserPromptPart,
    BaseToolReturnPart,
    RetryPromptPart,
    TextPart,
    ThinkingPart,
    CompactionPart,
)


def _render(content: object) -> str:
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content)
    except TypeError, ValueError:
        return str(content)


def _flat(content: object, limit: int) -> str:
    """One digest line holds one exchange, so newlines collapse to spaces."""
    return " ".join(_render(content).split())[:limit]


def _part_chars(part: ModelRequestPart | ModelResponsePart) -> int:
    if isinstance(part, BaseToolCallPart):
        return len(part.tool_name) + len(part.args_as_json_str())
    if isinstance(part, _CONTENT_PARTS):
        return len(_render(part.content))
    return 0


def _estimated_tokens(messages: Sequence[ModelMessage]) -> int:
    chars = sum(_part_chars(part) for msg in messages for part in msg.parts)
    return chars // _CHARS_PER_TOKEN


@dataclasses.dataclass(frozen=True)
class _TailSplit:
    """Where the kept tail starts, and how many exchanges it holds."""

    start: int
    exchanges: int


def _tail_split(messages: Sequence[ModelMessage]) -> _TailSplit:
    """The newest exchanges that fit the tail budget, on a pair boundary.

    ``start`` is ``len(messages)`` when no complete pair exists. An exchange
    below ``MIN_KEEP_RECENT_EXCHANGES`` is kept whatever it costs.
    """
    exchanges = 0
    kept_tokens = 0
    start = len(messages)
    i = len(messages) - 1
    while i >= 1:
        if not (
            isinstance(messages[i], ModelRequest)
            and isinstance(messages[i - 1], ModelResponse)
        ):
            i -= 1
            continue
        # The slice holds the pair plus anything newer not counted yet, so
        # every kept message is counted exactly once.
        pair_tokens = _estimated_tokens(messages[i - 1 : start])
        over_budget = kept_tokens + pair_tokens > KEEP_RECENT_EXCHANGE_TOKENS
        if exchanges >= MIN_KEEP_RECENT_EXCHANGES and over_budget:
            break
        exchanges += 1
        kept_tokens += pair_tokens
        start = i - 1
        i -= 2
    if exchanges == 0:
        return _TailSplit(len(messages), 0)
    # A dropped middle must end on a request, so every call it holds keeps the
    # return that answers it.
    while start > 1 and isinstance(messages[start - 1], ModelResponse):
        start -= 1
    return _TailSplit(start, exchanges)


def _middle_results(middle: Sequence[ModelMessage]) -> dict[str, str]:
    out: dict[str, str] = {}
    for msg in middle:
        if not isinstance(msg, ModelRequest):
            continue
        for part in msg.parts:
            if isinstance(part, BaseToolReturnPart):
                out[part.tool_call_id] = _flat(part.content, _RESULT_HEAD_CHARS)
            elif isinstance(part, RetryPromptPart) and part.tool_call_id:
                head = _flat(part.content, _RESULT_HEAD_CHARS)
                out[part.tool_call_id] = f"retry: {head}"
    return out


def _user_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence):
        return " ".join(item for item in content if isinstance(item, str))
    return ""


def _digest_lines(middle: Sequence[ModelMessage]) -> list[str]:
    results = _middle_results(middle)
    lines: list[str] = []
    for msg in middle:
        if isinstance(msg, ModelRequest):
            for req_part in msg.parts:
                if isinstance(req_part, UserPromptPart):
                    text = _user_text(req_part.content)
                    if text.strip():
                        lines.append(f"- user said: {_flat(text, _RESULT_HEAD_CHARS)}")
            continue
        for part in msg.parts:
            if isinstance(part, TextPart):
                if part.content.strip():
                    lines.append(f"- said: {_flat(part.content, _RESULT_HEAD_CHARS)}")
            elif isinstance(part, BaseToolCallPart):
                args = _flat(part.args_as_json_str(), _ARGS_HEAD_CHARS)
                result = results.get(part.tool_call_id, "(no result recorded)")
                lines.append(f"- {part.tool_name}({args}) -> {result}")
    return lines


def _assemble_digest(lines: Sequence[str], *, omitted: bool) -> str:
    opening = [_DIGEST_OPENING, _OMITTED_MARKER] if omitted else [_DIGEST_OPENING]
    return "\n".join([*opening, *lines, _DIGEST_CLOSING])


_USER_LINE_PREFIX = "- user said: "
_DIGEST_FRAMING = frozenset({_DIGEST_OPENING, _OMITTED_MARKER, _DIGEST_CLOSING})


def _digest_body(digest: str) -> list[str]:
    """The lines of a digest, without the framing that wraps them."""
    return [line for line in digest.split("\n") if line not in _DIGEST_FRAMING]


def _head_without_digests(
    head: ModelRequest,
) -> tuple[list[ModelRequestPart], list[str]]:
    """The head's own parts, and the lines of the digests it already carries.

    The head holds exactly one digest, so an earlier one is carried into the
    new digest instead of kept beside it.
    """
    kept: list[ModelRequestPart] = []
    prior: list[str] = []
    for part in head.parts:
        content = part.content if isinstance(part, UserPromptPart) else None
        if isinstance(content, str) and content.startswith(_DIGEST_OPENING):
            prior.extend(_digest_body(content))
            continue
        kept.append(part)
    return kept, prior


def _build_digest(
    middle: Sequence[ModelMessage],
    prior_lines: Sequence[str] = (),
) -> str:
    lines = [*prior_lines, *_digest_lines(middle)]
    whole = _assemble_digest(lines, omitted=False)
    if len(whole) <= _DIGEST_CHAR_CAP:
        return whole
    # Newest dropped work is the most relevant, so the cap keeps the tail.
    # A user's own words are constraints, so they survive the cap regardless
    # of age.
    budget = _DIGEST_CHAR_CAP - len(_assemble_digest((), omitted=True))
    keep = [line.startswith(_USER_LINE_PREFIX) for line in lines]
    used = sum(len(line) + 1 for line, held in zip(lines, keep, strict=True) if held)
    for i in range(len(lines) - 1, -1, -1):
        if keep[i]:
            continue
        used += len(lines[i]) + 1
        if used > budget:
            break
        keep[i] = True
    kept = [line for line, held in zip(lines, keep, strict=True) if held]
    return _assemble_digest(kept, omitted=True)


def _orphan_free(messages: Sequence[ModelMessage]) -> bool:
    call_ids, satisfied_ids, _, _ = _collect_ids(messages)
    return call_ids == satisfied_ids


def _compaction_plan(
    messages: Sequence[ModelMessage],
) -> tuple[ModelRequest, _TailSplit] | None:
    """The head request and the tail split, or ``None`` to leave the history.

    The head must carry the run's prompt and the result must still end with a
    ``ModelRequest``, so a history of another shape is left alone.
    """
    if _estimated_tokens(messages) <= COMPACT_AT_ESTIMATED_TOKENS:
        return None
    head = messages[0]
    if not isinstance(head, ModelRequest):
        return None
    if not isinstance(messages[-1], ModelRequest):
        return None
    split = _tail_split(messages)
    if split.start <= 1 or split.start >= len(messages):
        return None
    return head, split


def compact_exhausted_history(
    messages: list[ModelMessage],
) -> list[ModelMessage]:
    # A long dispatch grows its history until the token ceiling ends the run.
    # Past a threshold the older exchanges collapse into one digest carried by
    # the head request, keeping the wire context bounded.
    plan = _compaction_plan(messages)
    if plan is None:
        return list(messages)
    head, split = plan
    middle = messages[1 : split.start]
    head_parts, prior_lines = _head_without_digests(head)

    compacted: list[ModelMessage] = [
        dataclasses.replace(
            head,
            parts=[
                *head_parts,
                UserPromptPart(content=_build_digest(middle, prior_lines)),
            ],
        ),
        *messages[split.start :],
    ]
    if _orphan_free(messages) and not _orphan_free(compacted):
        return list(messages)

    logger.info(
        "in-run history compacted",
        input_messages=len(messages),
        output_messages=len(compacted),
        dropped_messages=len(middle),
        kept_exchanges=split.exchanges,
        input_estimated_tokens=_estimated_tokens(messages),
        output_estimated_tokens=_estimated_tokens(compacted),
    )
    return compacted


PHASE_HISTORY_PROCESSORS = (
    pair_tool_calls,
    elide_consumed_tool_results,
    compact_exhausted_history,
)
