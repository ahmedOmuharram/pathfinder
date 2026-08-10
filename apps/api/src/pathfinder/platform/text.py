"""Pure text utilities."""

import re

ELLIPSIS = "..."


def strip_html_tags(value: str | None) -> str:
    """Strip HTML tags from a string.

    Site-search highlights matches with ``<em>`` tags. This removes all tags.
    """
    return re.sub(r"</?[^>]+>", "", value or "").strip()


def truncate_on_word_boundary(value: str, max_chars: int) -> str:
    """Shorten to at most ``max_chars``, ending on a word and marked as cut.

    A raw slice reads as a complete sentence that happens to stop, which is
    how a truncated memory summary got mistaken for the whole thing. The
    result never exceeds ``max_chars`` including the trailing marker.
    """
    if len(value) <= max_chars:
        return value
    budget = max_chars - len(ELLIPSIS)
    if budget <= 0:
        return value[:max_chars]
    head = value[:budget]
    # When the next character is whitespace the slice already ends on a whole
    # word; trimming back anyway would drop a word that fits.
    if not value[budget].isspace():
        cut = head.rstrip().rfind(" ")
        if cut > 0:
            head = head[:cut]
    return head.rstrip() + ELLIPSIS
