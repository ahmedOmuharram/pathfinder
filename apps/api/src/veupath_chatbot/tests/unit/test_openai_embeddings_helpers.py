"""Tests for pure helpers in openai_embeddings.py."""

import pytest

from veupath_chatbot.integrations.embeddings.openai_embeddings import _chunks


class TestChunks:
    def test_exact_division(self) -> None:
        items = ["a", "b", "c", "d"]
        result = list(_chunks(items, size=2))
        assert result == [["a", "b"], ["c", "d"]]

    def test_remainder_chunk(self) -> None:
        items = ["a", "b", "c"]
        result = list(_chunks(items, size=2))
        assert result == [["a", "b"], ["c"]]

    def test_single_chunk(self) -> None:
        items = ["a", "b"]
        result = list(_chunks(items, size=10))
        assert result == [["a", "b"]]

    def test_empty_list(self) -> None:
        result = list(_chunks([], size=5))
        assert result == []

    def test_chunk_size_one(self) -> None:
        items = ["a", "b", "c"]
        result = list(_chunks(items, size=1))
        assert result == [["a"], ["b"], ["c"]]

    def test_chunk_size_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk size must be > 0"):
            list(_chunks(["a"], size=0))

    def test_negative_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk size must be > 0"):
            list(_chunks(["a"], size=-1))
