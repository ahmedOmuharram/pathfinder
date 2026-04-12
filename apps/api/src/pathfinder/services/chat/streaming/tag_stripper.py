"""Streaming tag stripper for ``<plan-thinking>`` blocks.

Strips ``<plan-thinking>…</plan-thinking>`` tags from a stream of text
deltas, accumulating partial matches in a buffer.
"""

import re

PLAN_THINKING_RE = re.compile(
    r"<plan-thinking>\s*(.*?)\s*</plan-thinking>",
    re.DOTALL,
)

_TAG_OPEN = "<plan-thinking>"
_TAG_CLOSE = "</plan-thinking>"


class StreamingTagStripper:
    """Strips ``<plan-thinking>...</plan-thinking>`` tags from a stream of text deltas.

    Accumulates partial tag matches in a buffer. Returns clean text (with tags
    removed) and any extracted thought strings on each ``feed()`` call.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._inside_tag = False

    def _consume_without_full_open_tag(self) -> str:
        """Emit safe clean text when no full opening tag exists in the buffer."""
        last_open_candidate = self._buffer.rfind("<")
        if last_open_candidate == -1:
            clean_text = self._buffer
            self._buffer = ""
            return clean_text

        suffix = self._buffer[last_open_candidate:]
        if _TAG_OPEN.startswith(suffix):
            clean_text = self._buffer[:last_open_candidate]
            self._buffer = suffix
            return clean_text

        clean_text = self._buffer
        self._buffer = ""
        return clean_text

    def feed(self, chunk: str) -> tuple[str, list[str]]:
        """Feed a text chunk, returning ``(clean_text, thoughts)``."""
        self._buffer += chunk
        clean_parts: list[str] = []
        thoughts: list[str] = []

        while True:
            if self._inside_tag:
                close_idx = self._buffer.find(_TAG_CLOSE)
                if close_idx == -1:
                    # Still inside tag, waiting for close
                    break
                thought_text = self._buffer[:close_idx].strip()
                if thought_text:
                    thoughts.append(thought_text)
                self._buffer = self._buffer[close_idx + len(_TAG_CLOSE):]
                self._inside_tag = False
            else:
                open_idx = self._buffer.find(_TAG_OPEN)
                if open_idx == -1:
                    clean_text = self._consume_without_full_open_tag()
                    if clean_text:
                        clean_parts.append(clean_text)
                    break
                # Found opening tag
                if open_idx > 0:
                    clean_parts.append(self._buffer[:open_idx])
                self._buffer = self._buffer[open_idx + len(_TAG_OPEN):]
                self._inside_tag = True

        return "".join(clean_parts), thoughts

    def flush(self) -> str:
        """Return any remaining buffered text and reset."""
        remaining = self._buffer
        self._buffer = ""
        self._inside_tag = False
        return remaining
