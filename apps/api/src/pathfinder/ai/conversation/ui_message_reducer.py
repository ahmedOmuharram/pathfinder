from __future__ import annotations

from typing import Any

from pathfinder.ai.conversation._chunk_handlers import _apply_chunk
from pathfinder.ai.conversation._chunk_state import Chunk, _new_state


def reduce_chunks(
    chunks: list[Chunk],
    default_message_id: str,
) -> dict[str, Any]:
    state = _new_state(default_message_id)
    for chunk in chunks:
        _apply_chunk(state, chunk)
    return state.message


def split_into_turns(chunks: list[Chunk]) -> list[list[Chunk]]:
    """Split a chunk log into per-turn slices on ``done`` boundaries.

    Each slice ends with the ``done`` chunk that terminated it. A trailing
    slice with no ``done`` represents an in-flight turn the snapshot caught
    mid-stream.
    """
    turns: list[list[Chunk]] = []
    current: list[Chunk] = []
    for chunk in chunks:
        current.append(chunk)
        if chunk.get("type") == "done":
            turns.append(current)
            current = []
    if current:
        turns.append(current)
    return turns


USER_MESSAGE_CHUNK_TYPE = "user-message"
SYSTEM_MESSAGE_CHUNK_TYPE = "system-message"
ASSISTANT_MESSAGE_CHUNK_TYPE = "assistant-message"


def user_message_chunk(
    *,
    message_id: str,
    parts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "type": USER_MESSAGE_CHUNK_TYPE,
        "message": {"id": message_id, "role": "user", "parts": parts},
    }


def system_message_chunk(
    *,
    message_id: str,
    parts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "type": SYSTEM_MESSAGE_CHUNK_TYPE,
        "message": {"id": message_id, "role": "system", "parts": parts},
    }


_ENVELOPE_CHUNK_TYPES = {
    USER_MESSAGE_CHUNK_TYPE,
    SYSTEM_MESSAGE_CHUNK_TYPE,
    ASSISTANT_MESSAGE_CHUNK_TYPE,
}


def reduce_chunks_to_messages(
    chunks: list[Chunk],
    fallback_id_prefix: str = "msg",
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    pending: list[Chunk] = []
    assistant_index = 0
    for chunk in chunks:
        if chunk.get("type") in _ENVELOPE_CHUNK_TYPES:
            if pending:
                messages.append(
                    reduce_chunks(
                        pending,
                        f"{fallback_id_prefix}-{assistant_index}",
                    )
                )
                assistant_index += 1
                pending = []
            raw = chunk.get("message")
            if isinstance(raw, dict):
                messages.append(raw)
            continue
        pending.append(chunk)
        if chunk.get("type") == "done":
            messages.append(
                reduce_chunks(
                    pending,
                    f"{fallback_id_prefix}-{assistant_index}",
                )
            )
            assistant_index += 1
            pending = []
    if pending:
        messages.append(
            reduce_chunks(
                pending,
                f"{fallback_id_prefix}-{assistant_index}",
            )
        )
    return messages


__all__ = [
    "ASSISTANT_MESSAGE_CHUNK_TYPE",
    "SYSTEM_MESSAGE_CHUNK_TYPE",
    "USER_MESSAGE_CHUNK_TYPE",
    "reduce_chunks",
    "reduce_chunks_to_messages",
    "split_into_turns",
    "system_message_chunk",
    "user_message_chunk",
]
