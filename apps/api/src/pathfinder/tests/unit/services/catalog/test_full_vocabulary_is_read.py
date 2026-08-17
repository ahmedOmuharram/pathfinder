"""Every reader of a vocabulary sees all of it, and never the tree root sentinel."""

from __future__ import annotations

from pathfinder.domain.parameters.wdk_vocab import (
    FAKE_ALL_SENTINEL,
    VocabOption,
    WDKTreeBoxVocabNode,
    WDKVocabNodeData,
    flatten_vocab,
)
from pathfinder.services.catalog.param_dag import (
    _apply_override,
    _open_slot,
    _single_valid_value,
    _vocab_signature,
    _VocabLedger,
)
from pathfinder.services.catalog.param_formatting import ParameterInfo


def _many(n: int) -> list[VocabOption]:
    return [VocabOption(value=f"GO:{i:07d}", display=f"term {i}") for i in range(n)]


def _tree_with_sentinel_root_and_a_repeat() -> WDKTreeBoxVocabNode:
    """A synthetic root over 25 leaf terms, one of which WDK lists twice."""
    terms = [f"GO:{i:07d}" for i in range(25)]
    terms.insert(5, terms[3])
    return WDKTreeBoxVocabNode(
        data=WDKVocabNodeData(term=FAKE_ALL_SENTINEL, display="All"),
        children=[
            WDKTreeBoxVocabNode(data=WDKVocabNodeData(term=t, display=f"term {t}"))
            for t in terms
        ],
    )


def _param(
    *, allowed: list[VocabOption] | None, leaves: list[VocabOption]
) -> ParameterInfo:
    return ParameterInfo(
        name="go_typeahead",
        display_name="GO term",
        type="multi-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        allowed_values=allowed,
        vocab_leaves=leaves,
    )


class TestVocabularyIsTheWholeList:
    def test_the_capped_list_is_not_the_vocabulary(self) -> None:
        full = _many(300)
        info = _param(allowed=full[:50], leaves=full)

        assert len(info.vocabulary()) == 300

    def test_the_sentinel_is_not_an_option(self) -> None:
        tree = WDKTreeBoxVocabNode(
            data=WDKVocabNodeData(term=FAKE_ALL_SENTINEL, display="All"),
            children=[
                WDKTreeBoxVocabNode(
                    data=WDKVocabNodeData(term="Plasmodium", display="Plasmodium")
                )
            ],
        )

        assert [o.value for o in flatten_vocab(tree)] == ["Plasmodium"]

    def test_a_repeated_option_is_offered_once(self) -> None:
        repeated = VocabOption(value="GO:0000001", display="term 1")
        info = _param(
            allowed=None,
            leaves=[
                repeated,
                repeated,
                VocabOption(value="GO:0000002", display="term 2"),
            ],
        )

        assert [o.value for o in info.vocabulary()] == ["GO:0000001", "GO:0000002"]


class TestReadersUseIt:
    def test_an_override_matches_beyond_the_cap(self) -> None:
        full = _many(300)
        info = _param(allowed=full[:50], leaves=full)

        assert _apply_override(info, "term 299") == "GO:0000299"

    def test_an_open_slot_offers_a_tree_box_vocabulary(self) -> None:
        leaves = flatten_vocab(_tree_with_sentinel_root_and_a_repeat())
        info = _param(allowed=None, leaves=leaves)

        slot = _open_slot(info)

        assert FAKE_ALL_SENTINEL not in slot.options
        assert len(set(slot.options)) == len(slot.options)
        assert slot.options == [f"GO:{i:07d}" for i in range(20)]


class TestTheLedgerSeesTreeBoxVocabularies:
    def test_a_tree_box_param_has_a_signature(self) -> None:
        info = _param(allowed=None, leaves=_many(3))

        assert _vocab_signature(info) is not None

    def test_a_sibling_taking_a_tree_box_value_is_a_duplicate(self) -> None:
        info = _param(allowed=None, leaves=_many(3))
        signature = _vocab_signature(info)
        assert signature is not None
        ledger = _VocabLedger()
        ledger.claim(signature, "GO:0000001", "sample_ref", pinned=True)

        assert ledger.duplicates_sibling(info, "GO:0000001")

    def test_a_single_leaf_tree_box_auto_resolves(self) -> None:
        info = _param(allowed=None, leaves=_many(1))

        assert _single_valid_value(info) == "GO:0000000"
