"""The phyletic code lookup reads its clade tree from the search parameters."""

from __future__ import annotations

from typing import Any

import pytest

from pathfinder.domain.parameters.wdk_vocab import WDKVocabTerm
from pathfinder.integrations.veupathdb.phyletic_tree import phyletic_tree_of
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKParameter,
    WDKStringParam,
)
from pathfinder.services.catalog import param_phyletic


def _term(code: str, display: str) -> WDKVocabTerm:
    return WDKVocabTerm((code, display, None))


def _params() -> list[WDKParameter]:
    return [
        WDKStringParam(name="profile_pattern", is_visible=False),
        WDKStringParam(name="included_species", allow_empty_value=True),
        WDKStringParam(name="excluded_species", allow_empty_value=True),
        WDKEnumParam(
            name="phyletic_term_map",
            type="multi-pick-vocabulary",
            vocabulary=[
                _term("ALL", "Root"),
                _term("EUKA", "Eukaryota"),
                _term("MAMM", "Mammalia"),
                _term("hsap", "Homo sapiens REF"),
                _term("pfal", "Plasmodium falciparum 3D7"),
            ],
        ),
        WDKEnumParam(
            name="phyletic_indent_map",
            type="multi-pick-vocabulary",
            vocabulary=[
                _term("EUKA", "1"),
                _term("MAMM", "2"),
                _term("hsap", "3"),
                _term("pfal", "2"),
            ],
        ),
    ]


@pytest.fixture(autouse=True)
def _no_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rank by tree order, so the test asserts the entries and not the model."""

    async def _tree_order(
        _query: str, candidates: list[tuple[str, str, bool]]
    ) -> list[tuple[str, str, bool]]:
        return candidates

    monkeypatch.setattr(param_phyletic, "_rank_by_semantic_similarity", _tree_order)


class TestTheMatchesDescribeTheTree:
    @staticmethod
    async def _matches() -> list[Any]:
        tree = phyletic_tree_of(_params())
        assert tree is not None
        return await param_phyletic._match_phyletic_entries(tree, "mammal")

    async def test_the_synthetic_root_is_not_a_match(self) -> None:
        assert all(m["code"] != "ALL" for m in await self._matches())

    async def test_a_clade_is_reported_as_a_group(self) -> None:
        by_code = {m["code"]: m for m in await self._matches()}

        assert by_code["MAMM"]["leaf"] is False
        assert by_code["EUKA"]["leaf"] is False

    async def test_a_species_is_reported_as_a_leaf(self) -> None:
        by_code = {m["code"]: m for m in await self._matches()}

        assert by_code["hsap"]["leaf"] is True
        assert by_code["pfal"]["leaf"] is True

    async def test_every_code_carries_its_label(self) -> None:
        by_code = {m["code"]: m for m in await self._matches()}

        assert by_code["pfal"]["label"] == "Plasmodium falciparum 3D7"

    async def test_an_empty_tree_matches_nothing(self) -> None:
        empty = phyletic_tree_of(
            [
                p
                for p in _params()
                if p.name not in {"phyletic_term_map", "phyletic_indent_map"}
            ]
            + [
                WDKEnumParam(
                    name="phyletic_term_map",
                    type="multi-pick-vocabulary",
                    vocabulary=[],
                ),
                WDKEnumParam(
                    name="phyletic_indent_map",
                    type="multi-pick-vocabulary",
                    vocabulary=[],
                ),
            ]
        )

        assert empty is not None
        assert await param_phyletic._match_phyletic_entries(empty, "mammal") == []
