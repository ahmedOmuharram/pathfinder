"""Tests for vocab_rendering.py — pure vocab tree display formatting."""

from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.catalog.vocab_rendering import (
    allowed_values,
    render_vocab_tree,
)


class TestRenderVocabTree:
    def test_simple_tree(self) -> None:
        tree: JSONObject = {
            "data": {"term": "Root"},
            "children": [
                {"data": {"term": "Child1"}, "children": []},
                {"data": {"term": "Child2"}, "children": []},
            ],
        }
        lines = render_vocab_tree(tree, max_lines=80)
        assert any("Child1" in line for line in lines)
        assert any("Child2" in line for line in lines)

    def test_truncation(self) -> None:
        tree: JSONObject = {
            "data": {"term": "Root"},
            "children": [
                {"data": {"term": f"Child{i}"}, "children": []} for i in range(100)
            ],
        }
        lines = render_vocab_tree(tree, max_lines=5)
        assert len(lines) <= 6  # 5 + possible truncation message

    def test_skips_fake_sentinel(self) -> None:
        tree: JSONObject = {
            "data": {"term": "@@fake@@"},
            "children": [
                {"data": {"term": "RealChild"}, "children": []},
            ],
        }
        lines = render_vocab_tree(tree, max_lines=80)
        assert not any("@@fake@@" in line for line in lines)
        assert any("RealChild" in line for line in lines)


class TestAllowedValues:
    def test_flat_list(self) -> None:
        vocab: JSONArray = [
            ["Pf3D7", "P. falciparum 3D7"],
            ["PvP01", "P. vivax P01"],
        ]
        result = allowed_values(vocab)
        values = [e["value"] for e in result if isinstance(e, dict)]
        assert "Pf3D7" in values
        assert "PvP01" in values

    def test_deduplicates(self) -> None:
        vocab: JSONArray = [
            ["Pf3D7", "P. falciparum 3D7"],
            ["Pf3D7", "P. falciparum 3D7 dup"],
        ]
        result = allowed_values(vocab)
        values = [e["value"] for e in result if isinstance(e, dict)]
        assert values.count("Pf3D7") == 1

    def test_caps_at_50(self) -> None:
        vocab: JSONArray = [[f"val{i}", f"display{i}"] for i in range(100)]
        result = allowed_values(vocab)
        assert len(result) == 50

    def test_empty(self) -> None:
        assert allowed_values(None) == []
        assert allowed_values([]) == []
