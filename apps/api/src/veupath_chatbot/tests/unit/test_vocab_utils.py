"""Tests for vocab_utils shared vocabulary matching functions."""

import pytest

from veupath_chatbot.domain.parameters.vocab_utils import (
    BROAD_VALUE_FIELDS,
    collect_leaf_terms,
    find_vocab_node,
    flatten_vocab,
    get_node_value,
    match_vocab_value,
    normalize_vocab_key,
    numeric_equivalent,
)
from veupath_chatbot.platform.errors import ValidationError


# ---------------------------------------------------------------------------
# numeric_equivalent
# ---------------------------------------------------------------------------
class TestNumericEquivalent:
    def test_matching_integers(self) -> None:
        assert numeric_equivalent("42", "42") is True

    def test_matching_floats(self) -> None:
        assert numeric_equivalent("3.14", "3.14") is True

    def test_integer_vs_float(self) -> None:
        assert numeric_equivalent("42", "42.0") is True

    def test_non_matching(self) -> None:
        assert numeric_equivalent("1", "2") is False

    def test_none_values(self) -> None:
        assert numeric_equivalent(None, "1") is False
        assert numeric_equivalent("1", None) is False
        assert numeric_equivalent(None, None) is False

    def test_empty_strings(self) -> None:
        assert numeric_equivalent("", "1") is False

    def test_non_numeric(self) -> None:
        assert numeric_equivalent("abc", "1") is False

    def test_whitespace_handling(self) -> None:
        assert numeric_equivalent("  42  ", "42") is True

    def test_precision_tolerance(self) -> None:
        """Values within rel_tol=1e-9 should match."""
        assert numeric_equivalent("1.0000000001", "1.0000000002") is True

    def test_large_precision_difference(self) -> None:
        assert numeric_equivalent("1.0", "1.001") is False

    def test_negative_numbers(self) -> None:
        assert numeric_equivalent("-5", "-5.0") is True
        assert numeric_equivalent("-5", "5") is False

    def test_scientific_notation(self) -> None:
        assert numeric_equivalent("1e3", "1000") is True

    def test_inf_returns_false(self) -> None:
        assert numeric_equivalent("inf", "inf") is False

    def test_nan_returns_false(self) -> None:
        assert numeric_equivalent("nan", "nan") is False

    def test_zero(self) -> None:
        assert numeric_equivalent("0", "0.0") is True
        assert numeric_equivalent("-0", "0") is True


# ---------------------------------------------------------------------------
# normalize_vocab_key
# ---------------------------------------------------------------------------
class TestNormalizeVocabKey:
    def test_strips_whitespace(self) -> None:
        assert normalize_vocab_key("  hello  ") == "hello"

    def test_lowercases(self) -> None:
        assert normalize_vocab_key("Hello World") == "hello world"

    def test_collapses_whitespace(self) -> None:
        assert normalize_vocab_key("hello   world") == "hello world"

    def test_handles_tabs_and_newlines(self) -> None:
        assert normalize_vocab_key("hello\t\nworld") == "hello world"

    def test_empty_string(self) -> None:
        assert normalize_vocab_key("") == ""

    def test_already_normalized(self) -> None:
        assert normalize_vocab_key("hello") == "hello"


# ---------------------------------------------------------------------------
# flatten_vocab
# ---------------------------------------------------------------------------
class TestFlattenVocab:
    """Tests for the flatten_vocab function."""

    def test_list_of_pairs(self) -> None:
        vocab = [["val1", "Display 1"], ["val2", "Display 2"]]
        entries = flatten_vocab(vocab)
        assert len(entries) == 2
        assert entries[0] == {"display": "Display 1", "value": "val1"}
        assert entries[1] == {"display": "Display 2", "value": "val2"}

    def test_list_of_single_item_lists(self) -> None:
        vocab = [["val1"], ["val2"]]
        entries = flatten_vocab(vocab)
        assert len(entries) == 2
        # display defaults to value when only one item
        assert entries[0] == {"display": "val1", "value": "val1"}

    def test_list_of_plain_strings(self) -> None:
        vocab = ["a", "b", "c"]
        entries = flatten_vocab(vocab)
        assert len(entries) == 3
        assert entries[0] == {"display": "a", "value": "a"}

    def test_list_of_dicts(self) -> None:
        vocab = [
            {"term": "t1", "display": "D1"},
            {"term": "t2", "display": "D2"},
        ]
        entries = flatten_vocab(vocab)
        assert len(entries) == 2
        # prefer_term=False by default, so value comes from value or term
        assert entries[0]["value"] == "t1"
        assert entries[0]["display"] == "D1"

    def test_list_of_dicts_with_value_field(self) -> None:
        vocab = [
            {"value": "v1", "term": "t1", "display": "D1"},
        ]
        entries = flatten_vocab(vocab, prefer_term=False)
        assert entries[0]["value"] == "v1"

    def test_list_of_dicts_prefer_term(self) -> None:
        vocab = [
            {"value": "v1", "term": "t1", "display": "D1"},
        ]
        entries = flatten_vocab(vocab, prefer_term=True)
        assert entries[0]["value"] == "t1"

    def test_tree_vocab(self) -> None:
        vocab = {
            "data": {"term": "root", "display": "Root"},
            "children": [
                {"data": {"term": "child1", "display": "Child 1"}, "children": []},
                {"data": {"term": "child2", "display": "Child 2"}, "children": []},
            ],
        }
        entries = flatten_vocab(vocab, prefer_term=True)
        assert len(entries) == 3
        terms = [e["value"] for e in entries]
        assert "root" in terms
        assert "child1" in terms
        assert "child2" in terms

    def test_nested_tree_vocab(self) -> None:
        vocab = {
            "data": {"term": "root", "display": "Root"},
            "children": [
                {
                    "data": {"term": "parent", "display": "Parent"},
                    "children": [
                        {"data": {"term": "leaf", "display": "Leaf"}, "children": []},
                    ],
                },
            ],
        }
        entries = flatten_vocab(vocab, prefer_term=True)
        assert len(entries) == 3
        terms = [e["value"] for e in entries]
        assert terms == ["root", "parent", "leaf"]

    def test_empty_dict_vocab(self) -> None:
        entries = flatten_vocab({})
        assert entries == []

    def test_empty_list_vocab(self) -> None:
        entries = flatten_vocab([])
        assert entries == []

    def test_list_with_none_first_element_skipped(self) -> None:
        vocab = [[None, "display"]]
        entries = flatten_vocab(vocab)
        assert entries == []

    def test_list_with_none_second_element(self) -> None:
        vocab = [["val", None]]
        entries = flatten_vocab(vocab)
        assert len(entries) == 1
        assert entries[0] == {"display": "val", "value": "val"}

    def test_tree_with_non_dict_children_skipped(self) -> None:
        vocab = {
            "data": {"term": "root", "display": "Root"},
            "children": ["not_a_dict", 42],
        }
        entries = flatten_vocab(vocab, prefer_term=True)
        assert len(entries) == 1
        assert entries[0]["value"] == "root"

    def test_tree_with_non_list_children(self) -> None:
        vocab = {
            "data": {"term": "root", "display": "Root"},
            "children": "not_a_list",
        }
        entries = flatten_vocab(vocab, prefer_term=True)
        assert len(entries) == 1

    def test_tree_with_non_dict_data(self) -> None:
        vocab = {
            "data": "not_a_dict",
            "children": [],
        }
        entries = flatten_vocab(vocab, prefer_term=True)
        assert len(entries) == 1
        assert entries[0] == {"display": None, "value": None}

    def test_numeric_values_in_list(self) -> None:
        vocab = [42, 3.14]
        entries = flatten_vocab(vocab)
        assert entries[0] == {"display": "42", "value": "42"}
        assert entries[1] == {"display": "3.14", "value": "3.14"}


# ---------------------------------------------------------------------------
# match_vocab_value
# ---------------------------------------------------------------------------
class TestMatchVocabValue:
    """Tests for the shared match_vocab_value function."""

    def test_no_vocab_returns_value_as_is(self) -> None:
        result = match_vocab_value(vocab=None, param_name="p", value="hello")
        assert result == "hello"

    def test_empty_list_vocab_returns_value_as_is(self) -> None:
        result = match_vocab_value(vocab=[], param_name="p", value="hello")
        assert result == "hello"

    def test_exact_display_match(self) -> None:
        vocab = [["val1", "Display One"], ["val2", "Display Two"]]
        result = match_vocab_value(vocab=vocab, param_name="p", value="Display One")
        assert result == "val1"

    def test_exact_value_match(self) -> None:
        vocab = [["val1", "Display One"]]
        result = match_vocab_value(vocab=vocab, param_name="p", value="val1")
        assert result == "val1"

    def test_numeric_match(self) -> None:
        vocab = [["42.0", "42"]]
        result = match_vocab_value(vocab=vocab, param_name="p", value="42")
        assert result == "42.0"

    def test_no_match_raises(self) -> None:
        vocab = [["a", "A"], ["b", "B"]]
        with pytest.raises(ValidationError, match="Invalid parameter value"):
            match_vocab_value(vocab=vocab, param_name="test_param", value="nonexistent")

    def test_tree_vocab_match(self) -> None:
        vocab = {
            "data": {"display": "Root", "term": "root_val"},
            "children": [
                {"data": {"display": "Child", "term": "child_val"}, "children": []}
            ],
        }
        result = match_vocab_value(vocab=vocab, param_name="p", value="Child")
        assert result == "child_val"

    def test_whitespace_stripped(self) -> None:
        vocab = [["val1", "Display"]]
        result = match_vocab_value(vocab=vocab, param_name="p", value="  Display  ")
        assert result == "val1"

    def test_numeric_equivalent_on_value_field(self) -> None:
        vocab = [["100.0", "hundred"]]
        result = match_vocab_value(vocab=vocab, param_name="p", value="100")
        assert result == "100.0"

    def test_display_match_takes_priority_over_value_match(self) -> None:
        """When display matches first entry, return its value."""
        vocab = [["internal", "display_name"]]
        result = match_vocab_value(vocab=vocab, param_name="p", value="display_name")
        assert result == "internal"

    def test_error_message_includes_param_name_and_value(self) -> None:
        vocab = [["a", "A"]]
        with pytest.raises(ValidationError) as exc_info:
            match_vocab_value(vocab=vocab, param_name="my_param", value="bad")
        assert "my_param" in (exc_info.value.detail or "")
        assert "bad" in (exc_info.value.detail or "")


# ---------------------------------------------------------------------------
# get_node_value
# ---------------------------------------------------------------------------


def _make_vocab_tree() -> dict:
    return {
        "data": {"display": "@@fake@@", "value": "root"},
        "children": [
            {
                "data": {"display": "Plasmodium", "value": "plasmodium"},
                "children": [
                    {
                        "data": {"display": "P. falciparum 3D7", "value": "pf3d7"},
                        "children": [],
                    },
                    {
                        "data": {"display": "P. vivax", "value": "pvivax"},
                        "children": [],
                    },
                ],
            },
            {
                "data": {"display": "Toxoplasma", "value": "toxoplasma"},
                "children": [],
            },
        ],
    }


class TestGetNodeValue:
    def test_default_extracts_term(self) -> None:
        node = {"data": {"term": "the_term", "value": "the_value"}}
        assert get_node_value(node) == "the_term"

    def test_broad_fields_prefers_value(self) -> None:
        node = {"data": {"value": "the_value", "display": "Display"}}
        assert get_node_value(node, fields=BROAD_VALUE_FIELDS) == "the_value"

    def test_broad_fields_falls_back_to_id(self) -> None:
        node = {"data": {"id": "the_id", "display": "Display"}}
        assert get_node_value(node, fields=BROAD_VALUE_FIELDS) == "the_id"

    def test_broad_fields_falls_back_to_term(self) -> None:
        node = {"data": {"term": "the_term"}}
        assert get_node_value(node, fields=BROAD_VALUE_FIELDS) == "the_term"

    def test_broad_fields_falls_back_to_name(self) -> None:
        node = {"data": {"name": "the_name"}}
        assert get_node_value(node, fields=BROAD_VALUE_FIELDS) == "the_name"

    def test_broad_fields_falls_back_to_display(self) -> None:
        node = {"data": {"display": "the_display"}}
        assert get_node_value(node, fields=BROAD_VALUE_FIELDS) == "the_display"

    def test_empty_data_returns_none(self) -> None:
        node = {"data": {}}
        assert get_node_value(node) is None

    def test_no_data_key_returns_none(self) -> None:
        node = {}
        assert get_node_value(node) is None

    def test_non_string_values_converted(self) -> None:
        node = {"data": {"term": 42}}
        assert get_node_value(node) == "42"


# ---------------------------------------------------------------------------
# find_vocab_node (enhanced)
# ---------------------------------------------------------------------------
class TestFindVocabNode:
    def test_default_matches_term(self) -> None:
        tree = {
            "data": {"term": "root", "display": "Root"},
            "children": [
                {"data": {"term": "child", "display": "Child"}, "children": []},
            ],
        }
        assert find_vocab_node(tree, "child") is not None

    def test_default_matches_display(self) -> None:
        tree = {
            "data": {"term": "root", "display": "Root"},
            "children": [
                {"data": {"term": "child", "display": "Child"}, "children": []},
            ],
        }
        assert find_vocab_node(tree, "Child") is not None

    def test_broad_fields_matches_value(self) -> None:
        vocab = _make_vocab_tree()
        node = find_vocab_node(vocab, "plasmodium", fields=BROAD_VALUE_FIELDS)
        assert node is not None
        assert node["data"]["value"] == "plasmodium"

    def test_broad_fields_matches_display(self) -> None:
        vocab = _make_vocab_tree()
        node = find_vocab_node(vocab, "Plasmodium", fields=BROAD_VALUE_FIELDS)
        assert node is not None

    def test_normalize_matches_case_insensitive(self) -> None:
        vocab = _make_vocab_tree()
        node = find_vocab_node(
            vocab, "PLASMODIUM", fields=BROAD_VALUE_FIELDS, normalize=True
        )
        assert node is not None

    def test_no_match_returns_none(self) -> None:
        vocab = _make_vocab_tree()
        node = find_vocab_node(vocab, "nonexistent", fields=BROAD_VALUE_FIELDS)
        assert node is None

    def test_finds_in_children(self) -> None:
        vocab = _make_vocab_tree()
        node = find_vocab_node(vocab, "pf3d7", fields=BROAD_VALUE_FIELDS)
        assert node is not None
        assert node["data"]["value"] == "pf3d7"

    def test_without_normalize_no_case_folding(self) -> None:
        vocab = _make_vocab_tree()
        node = find_vocab_node(vocab, "PLASMODIUM", fields=BROAD_VALUE_FIELDS)
        assert node is None


# ---------------------------------------------------------------------------
# collect_leaf_terms (enhanced)
# ---------------------------------------------------------------------------
class TestCollectLeafTerms:
    def test_default_collects_term_field(self) -> None:
        node = {
            "data": {"term": "parent"},
            "children": [
                {"data": {"term": "leaf1"}, "children": []},
                {"data": {"term": "leaf2"}, "children": []},
            ],
        }
        assert collect_leaf_terms(node) == ["leaf1", "leaf2"]

    def test_broad_fields_collects_value_field(self) -> None:
        node = {"data": {"value": "leaf_val"}, "children": []}
        assert collect_leaf_terms(node, fields=BROAD_VALUE_FIELDS) == ["leaf_val"]

    def test_broad_fields_parent_returns_children(self) -> None:
        node = {
            "data": {"value": "parent"},
            "children": [
                {"data": {"value": "child1"}, "children": []},
                {"data": {"value": "child2"}, "children": []},
            ],
        }
        assert collect_leaf_terms(node, fields=BROAD_VALUE_FIELDS) == [
            "child1",
            "child2",
        ]

    def test_broad_fields_deep_nesting(self) -> None:
        node = {
            "data": {"value": "root"},
            "children": [
                {
                    "data": {"value": "mid"},
                    "children": [
                        {"data": {"value": "deep_leaf"}, "children": []},
                    ],
                },
            ],
        }
        assert collect_leaf_terms(node, fields=BROAD_VALUE_FIELDS) == ["deep_leaf"]

    def test_empty_data_skipped(self) -> None:
        node = {"data": {}, "children": []}
        assert collect_leaf_terms(node) == []

    def test_leaf_with_no_term_skipped(self) -> None:
        node = {"data": {"display": "only_display"}, "children": []}
        assert collect_leaf_terms(node) == []

    def test_leaf_with_no_term_but_broad_fields(self) -> None:
        node = {"data": {"display": "only_display"}, "children": []}
        assert collect_leaf_terms(node, fields=BROAD_VALUE_FIELDS) == ["only_display"]
