"""Tests for strategy graph metadata helpers."""

from veupath_chatbot.domain.strategy.metadata import derive_graph_metadata


class TestDeriveGraphMetadata:
    def test_short_name_unchanged(self) -> None:
        name, desc = derive_graph_metadata("Find kinase genes")
        assert name == "Find kinase genes"
        assert desc == "Find kinase genes"

    def test_long_name_truncated(self) -> None:
        long_goal = "A" * 100
        name, desc = derive_graph_metadata(long_goal)
        assert len(name) <= 80
        assert name.endswith("...")
        assert desc == long_goal

    def test_empty_defaults_to_strategy_draft(self) -> None:
        name, _desc = derive_graph_metadata("")
        assert name == "Strategy Draft"

    def test_none_defaults_to_strategy_draft(self) -> None:
        name, _desc = derive_graph_metadata(None)
        assert name == "Strategy Draft"

    def test_whitespace_collapsed(self) -> None:
        name, desc = derive_graph_metadata("  find   kinase   genes  ")
        assert name == "find kinase genes"
        assert desc == "find kinase genes"

    def test_exactly_80_chars_not_truncated(self) -> None:
        goal = "A" * 80
        name, _ = derive_graph_metadata(goal)
        assert name == goal
        assert "..." not in name
