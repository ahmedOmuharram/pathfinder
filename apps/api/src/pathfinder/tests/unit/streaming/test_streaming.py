"""Tests for the streaming tag stripper."""


from pathfinder.services.chat.streaming.tag_stripper import StreamingTagStripper


def test_tag_stripper_removes_plan_thinking() -> None:
    stripper = StreamingTagStripper()

    clean, thoughts = stripper.feed(
        "Hello <plan-thinking>internal reasoning</plan-thinking> world"
    )

    assert "plan-thinking" not in clean
    assert "internal reasoning" not in clean
    assert "Hello" in clean
    assert thoughts == ["internal reasoning"]

    remaining = stripper.flush()
    assert "world" in (clean + remaining)


def test_tag_stripper_handles_partial_tags_across_chunks() -> None:
    stripper = StreamingTagStripper()

    clean1, thoughts1 = stripper.feed("Before <plan-")
    clean2, thoughts2 = stripper.feed("thinking>secret thought</plan-thinking> after")

    assert thoughts1 == []
    assert thoughts2 == ["secret thought"]

    combined = clean1 + clean2 + stripper.flush()
    assert "Before" in combined
    assert "after" in combined
    assert "secret thought" not in combined
    assert "plan-thinking" not in combined


def test_tag_stripper_flush_returns_remaining() -> None:
    stripper = StreamingTagStripper()

    clean, thoughts = stripper.feed("some text")

    # The stripper buffers the last len("<plan-thinking>")-1 chars
    remaining = stripper.flush()

    full = clean + remaining
    assert full == "some text"
    assert thoughts == []


def test_tag_stripper_multiple_tags() -> None:
    stripper = StreamingTagStripper()

    clean, thoughts = stripper.feed(
        "A <plan-thinking>thought1</plan-thinking> B <plan-thinking>thought2</plan-thinking> C"
    )

    remaining = stripper.flush()
    full = clean + remaining

    assert thoughts == ["thought1", "thought2"]
    assert "A" in full
    assert "B" in full
    assert "C" in full
    assert "plan-thinking" not in full


def test_tag_stripper_empty_tag() -> None:
    stripper = StreamingTagStripper()

    clean, thoughts = stripper.feed(
        "prefix<plan-thinking></plan-thinking>suffix"
    )

    remaining = stripper.flush()
    full = clean + remaining

    # Empty tag content is stripped (empty string not added to thoughts)
    assert thoughts == []
    assert "prefix" in full
    assert "suffix" in full


def test_tag_stripper_unclosed_tag_stays_buffered() -> None:
    stripper = StreamingTagStripper()

    clean, thoughts = stripper.feed("before <plan-thinking>still thinking...")

    assert thoughts == []
    assert "still thinking" not in clean

    # Feed the close tag
    clean2, thoughts2 = stripper.feed("</plan-thinking> done")

    assert thoughts2 == ["still thinking..."]
    remaining = stripper.flush()
    full = clean + clean2 + remaining
    assert "before" in full
    assert "done" in full


def test_tag_stripper_preserves_text_without_tags() -> None:
    stripper = StreamingTagStripper()

    chunks = ["Hello ", "world, ", "no tags here."]
    parts: list[str] = []
    for chunk in chunks:
        clean, thoughts = stripper.feed(chunk)
        parts.append(clean)
        assert thoughts == []

    parts.append(stripper.flush())
    full = "".join(parts)
    assert full == "Hello world, no tags here."
