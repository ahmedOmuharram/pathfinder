"""Additional tests for StreamingTagStripper edge cases.

Covers nested content, consecutive tags, and interleaved text+tag patterns.
"""


from pathfinder.services.chat.streaming.tag_stripper import StreamingTagStripper


def test_tag_stripper_nested_content() -> None:
    """Tags with newlines and formatted content inside should be stripped."""
    stripper = StreamingTagStripper()

    content = (
        "Before "
        "<plan-thinking>\n"
        "Step 1: Find genes\n"
        "Step 2: Combine results\n"
        "Step 3: Filter by expression\n"
        "</plan-thinking>"
        " After"
    )
    clean, thoughts = stripper.feed(content)
    remaining = stripper.flush()
    full = clean + remaining

    assert len(thoughts) == 1
    assert "Step 1: Find genes" in thoughts[0]
    assert "Step 2: Combine results" in thoughts[0]
    assert "Step 3: Filter by expression" in thoughts[0]

    assert "Before" in full
    assert "After" in full
    assert "plan-thinking" not in full
    assert "Step 1" not in full


def test_tag_stripper_consecutive_tags() -> None:
    """Two tags back to back should both be extracted."""
    stripper = StreamingTagStripper()

    content = (
        "<plan-thinking>first thought</plan-thinking>"
        "<plan-thinking>second thought</plan-thinking>"
    )
    clean, thoughts = stripper.feed(content)
    remaining = stripper.flush()
    full = clean + remaining

    assert thoughts == ["first thought", "second thought"]
    # No visible content should remain (just whitespace at most)
    assert "first thought" not in full
    assert "second thought" not in full
    assert "plan-thinking" not in full


def test_tag_stripper_interleaved_text_and_tags() -> None:
    """Pattern: text, tag, text, tag — all text preserved, tags stripped."""
    stripper = StreamingTagStripper()

    parts = [
        "Hello ",
        "<plan-thinking>thinking about it</plan-thinking>",
        " middle text ",
        "<plan-thinking>more thinking</plan-thinking>",
        " goodbye",
    ]
    all_clean: list[str] = []
    all_thoughts: list[str] = []

    for part in parts:
        clean, thoughts = stripper.feed(part)
        all_clean.append(clean)
        all_thoughts.extend(thoughts)

    all_clean.append(stripper.flush())
    full = "".join(all_clean)

    assert all_thoughts == ["thinking about it", "more thinking"]
    assert "Hello" in full
    assert "middle text" in full
    assert "goodbye" in full
    assert "thinking about it" not in full
    assert "more thinking" not in full


def test_tag_stripper_tag_split_across_many_chunks() -> None:
    """A single tag split across 4+ chunks should still be handled correctly."""
    stripper = StreamingTagStripper()

    chunks = [
        "prefix ",
        "<plan",
        "-think",
        "ing>",
        "deep",
        " thought",
        "</plan",
        "-thinking>",
        " suffix",
    ]

    all_clean: list[str] = []
    all_thoughts: list[str] = []

    for chunk in chunks:
        clean, thoughts = stripper.feed(chunk)
        all_clean.append(clean)
        all_thoughts.extend(thoughts)

    all_clean.append(stripper.flush())
    full = "".join(all_clean)

    assert all_thoughts == ["deep thought"]
    assert "prefix" in full
    assert "suffix" in full
    assert "deep thought" not in full
    assert "plan-thinking" not in full


def test_tag_stripper_only_tags_no_text() -> None:
    """Input that is entirely tags should produce empty clean text."""
    stripper = StreamingTagStripper()

    content = "<plan-thinking>only a thought</plan-thinking>"
    clean, thoughts = stripper.feed(content)
    remaining = stripper.flush()
    full = clean + remaining

    assert thoughts == ["only a thought"]
    # Full text should be empty or whitespace-only
    assert full.strip() == ""
