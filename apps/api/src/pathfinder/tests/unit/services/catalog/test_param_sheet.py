"""The sheet shows a whole small vocabulary, a shortlist of a large one, and says which.

Ranking is lexical on purpose. Embedding a vocabulary takes 21 s for 500 options
and 238 s for 5,461 on the API container, and the sheet is built inside a tool
call the model waits on.
"""

from __future__ import annotations

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_sheet import DIRECT_MAX, TOP_K, build_sheet


def _param(
    name: str,
    leaves: list[VocabOption],
    *,
    depends: list[str] | None = None,
    tree: str | None = None,
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="multi-pick-vocabulary",
        required=True,
        is_visible=True,
        help="h",
        value_format="",
        vocab_leaves=leaves,
        vocab_depends_on=depends,
        allowed_values_tree=tree,
    )


def _go_terms(count: int) -> list[VocabOption]:
    return [VocabOption(value=f"GO:{i:07d}", display=f"term {i}") for i in range(count)]


def test_a_small_vocabulary_is_shown_whole() -> None:
    leaves = [VocabOption(value=f"v{i}", display=f"v{i}") for i in range(10)]

    [entry] = build_sheet([_param("p", leaves)], query="anything")

    assert len(entry.vocabulary) == 10
    assert entry.vocabulary_total == 10
    assert entry.vocabulary_note is None


def test_a_large_vocabulary_is_shortlisted_and_says_so() -> None:
    leaves = _go_terms(DIRECT_MAX + 500)
    leaves[-1] = VocabOption(value="GO:9999999", display="wanted term")

    [entry] = build_sheet([_param("go_typeahead", leaves)], query="the wanted term")

    assert len(entry.vocabulary) == TOP_K
    assert entry.vocabulary_total == DIRECT_MAX + 500
    assert entry.vocabulary[0].value == "GO:9999999"
    assert "get_parameter_options" in (entry.vocabulary_note or "")
    assert "most relevant to the request by name" in (entry.vocabulary_note or "")


def test_a_named_identifier_is_pinned_even_when_ranking_misses_it() -> None:
    leaves = _go_terms(DIRECT_MAX + 500)

    [entry] = build_sheet([_param("go_typeahead", leaves)], query="GO:0000650 please")

    assert any(o.value == "GO:0000650" for o in entry.vocabulary)


def _domain_families(count: int) -> list[VocabOption]:
    """A typeahead vocabulary, written the way WDK writes one: accession, label."""
    return [
        VocabOption(
            value=f"PF9{i:04d} : InterPro domain {i}",
            display=f"PF9{i:04d} : InterPro domain {i}",
        )
        for i in range(count)
    ]


def test_a_named_accession_is_pinned_when_the_label_is_not_written_out() -> None:
    # Every entry shares the request's generic words, so ranking is a tie and
    # the wanted entry sits outside the shortlist on order alone.
    leaves = _domain_families(700)
    leaves[600] = VocabOption(value="PF00069 : Pkinase", display="PF00069 : Pkinase")

    [entry] = build_sheet(
        [_param("domain_typeahead", leaves)], query="InterPro domain PF00069 (Pkinase)"
    )

    assert entry.vocabulary[0].value == "PF00069 : Pkinase"


def test_a_short_leading_word_is_not_an_accession_and_is_not_pinned() -> None:
    leaves = _domain_families(700)
    leaves[600] = VocabOption(value="ABC : Alpha kinase", display="ABC : Alpha kinase")

    [entry] = build_sheet(
        [_param("domain_typeahead", leaves)], query="InterPro domain ABC"
    )

    assert all(o.value != "ABC : Alpha kinase" for o in entry.vocabulary)


def test_shared_words_rank_an_option_above_an_unrelated_one() -> None:
    leaves = _go_terms(300)
    leaves[10] = VocabOption(value="GO:0005515", display="protein binding")
    leaves[20] = VocabOption(value="GO:0016301", display="kinase activity")
    leaves[30] = VocabOption(value="GO:0016772", display="transferase kinase")

    [entry] = build_sheet([_param("go_typeahead", leaves)], query="kinase activity")

    order = [o.value for o in entry.vocabulary]
    assert order.index("GO:0016301") < order.index("GO:0005515")
    # Two shared words beat one, one beats none.
    assert order.index("GO:0016301") < order.index("GO:0016772")
    assert order.index("GO:0016772") < order.index("GO:0005515")


def test_short_query_words_do_not_rank() -> None:
    leaves = _go_terms(300)
    leaves[10] = VocabOption(value="GO:8888888", display="an in of")

    [entry] = build_sheet([_param("go_typeahead", leaves)], query="in an of")

    # Nothing scored, so the vocabulary keeps its original order.
    assert [o.value for o in entry.vocabulary] == [o.value for o in leaves[:TOP_K]]


def test_a_dependent_vocabulary_names_its_parents() -> None:
    leaves = [VocabOption(value="a", display="a")]

    [entry] = build_sheet([_param("child", leaves, depends=["parent"])], query="")

    assert entry.depends_on == ["parent"]
    assert "parent" in (entry.vocabulary_note or "")


def test_a_tree_vocabulary_says_a_parent_selects_its_children() -> None:
    leaves = [VocabOption(value="pfal", display="P. falciparum")]

    [entry] = build_sheet(
        [_param("organism", leaves, tree="Plasmodium\n  P. falciparum")], query=""
    )

    assert entry.is_tree is True
    assert "A parent term selects all of its children." in (entry.vocabulary_note or "")


def test_a_flat_vocabulary_is_not_a_tree() -> None:
    leaves = [VocabOption(value="a", display="a")]

    [entry] = build_sheet([_param("p", leaves)], query="")

    assert entry.is_tree is False


def test_hidden_params_are_not_on_the_sheet() -> None:
    hidden = ParameterInfo(
        name="WebServicesPath",
        display_name="",
        type="string",
        required=True,
        is_visible=False,
        help="",
        value_format="",
        default_value="dflt",
    )

    assert build_sheet([hidden], query="") == []
