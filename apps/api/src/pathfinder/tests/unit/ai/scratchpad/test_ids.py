from __future__ import annotations

import re

from pathfinder.domain.scratchpad.ids import approx_body_tokens, mint_note_id


class TestMintNoteId:
    def test_format(self) -> None:
        nid = mint_note_id()
        assert re.fullmatch(r"n-[0-9a-f]{6}", nid), nid

    def test_distinct_ids(self) -> None:
        ids = {mint_note_id() for _ in range(1000)}
        assert len(ids) > 950  # ~16.7M space; some duplicates extremely unlikely


class TestApproxBodyTokens:
    def test_empty(self) -> None:
        assert approx_body_tokens("") == 0

    def test_short(self) -> None:
        # "hello world" = 11 chars -> 2 tokens (floor division)
        assert approx_body_tokens("hello world") == 2

    def test_known_string(self) -> None:
        assert approx_body_tokens("x" * 400) == 100
