"""A vocabulary entry's third element is the parent term, and the phyletic tree
is built from it.

The excerpt below is the head of the ``phyletic_term_map`` and
``phyletic_indent_map`` vocabularies of ``GenesByOrthologPattern``, read with::

    curl -s 'https://plasmodb.org/plasmo/service/record-types/transcript/searches/GenesByOrthologPattern?expandParams=true'
"""

from __future__ import annotations

from pydantic import TypeAdapter

from pathfinder.domain.parameters.phyletic import PhyleticTree
from pathfinder.domain.parameters.wdk_vocab import WDKVocabTerm
from pathfinder.integrations.veupathdb.wdk_parameters import WDKEnumParam

_TERM_MAP: list[list[str | None]] = [
    ["BACT", "Bacteria", None],
    ["FIRM", "Firmicutes", "BACT"],
    ["bant", "Bacillus anthracis", "FIRM"],
    ["bsub", "Bacillus subtilis subsp. subtilis str. 168", "FIRM"],
    ["EUKA", "Eukaryota", None],
    ["MAMM", "Mammalia", "EUKA"],
    ["hsap", "Homo sapiens REF", "MAMM"],
]

_INDENT_MAP: list[list[str | None]] = [
    ["BACT", "1", None],
    ["FIRM", "2", "BACT"],
    ["bant", "3", "FIRM"],
    ["bsub", "3", "FIRM"],
    ["EUKA", "1", None],
    ["MAMM", "2", "EUKA"],
    ["hsap", "3", "MAMM"],
]


class TestTheThirdElementIsTheParentTerm:
    def test_a_nested_entry_parses_and_states_its_parent(self) -> None:
        entry = WDKVocabTerm(("FIRM", "Firmicutes", "BACT"))

        assert (entry.term, entry.display, entry.parent) == (
            "FIRM",
            "Firmicutes",
            "BACT",
        )

    def test_a_root_entry_has_no_parent(self) -> None:
        entry = WDKVocabTerm(("BACT", "Bacteria", None))

        assert entry.parent is None

    def test_the_live_parameter_parses(self) -> None:
        param = WDKEnumParam.model_validate(
            {
                "name": "phyletic_term_map",
                "type": "multi-pick-vocabulary",
                "displayType": "checkBox",
                "vocabulary": _TERM_MAP,
            }
        )

        terms = TypeAdapter(list[WDKVocabTerm]).validate_python(param.vocabulary)

        assert [t.parent for t in terms] == [
            None,
            "BACT",
            "FIRM",
            "FIRM",
            None,
            "EUKA",
            "MAMM",
        ]


class TestTheTreeIsBuiltFromTheParentTerm:
    def _tree(self) -> PhyleticTree:
        return PhyleticTree.from_vocab(
            [WDKVocabTerm(tuple(row)) for row in _TERM_MAP],
            [WDKVocabTerm(tuple(row)) for row in _INDENT_MAP],
        )

    def test_the_roots_are_the_entries_with_no_parent(self) -> None:
        assert [node.code for node in self._tree().roots] == ["BACT", "EUKA"]

    def test_a_clade_expands_to_the_species_under_it(self) -> None:
        states = self._tree().leaf_states(included=["FIRM"], excluded=["MAMM"])

        assert states == {"bant": "include", "bsub": "include", "hsap": "exclude"}

    def test_an_absent_indent_map_keeps_the_parent_structure(self) -> None:
        tree = PhyleticTree.from_vocab(
            [WDKVocabTerm(tuple(row)) for row in _TERM_MAP],
            [],
        )

        assert [node.code for node in tree.roots] == ["BACT", "EUKA"]
        assert tree.leaf_states(included=["EUKA"], excluded=[]) == {"hsap": "include"}
