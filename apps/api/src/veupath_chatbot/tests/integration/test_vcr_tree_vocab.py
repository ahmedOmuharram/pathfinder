"""VCR-backed integration tests for tree vocabulary parameter handling.

Tests that PathFinder correctly handles parent and leaf organism values
against real WDK API responses. All site/organism values are discovered
dynamically from the assigned random site.

Record:
    WDK_AUTH_EMAIL=<email> WDK_AUTH_PASSWORD=<pw> \
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_tree_vocab.py -v --record-mode=all

Replay:
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_tree_vocab.py -v
"""

import pytest

from veupath_chatbot.domain.parameters._decode_values import decode_values
from veupath_chatbot.domain.parameters.canonicalize import ParameterCanonicalizer
from veupath_chatbot.domain.parameters.specs import adapt_param_specs_from_search
from veupath_chatbot.domain.parameters.vocab_utils import (
    flatten_vocab,
    match_vocab_value,
)
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.tests.conftest import (
    discover_leaf_organism,
    discover_organism_vocab,
    discover_parent_organism,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_organism_specs(api: StrategyAPI) -> dict:
    """Fetch the full organism parameter specs from the api's site."""
    response = await api.client.get_search_details(
        "transcript", "GenesByTaxon", expand_params=True,
    )
    specs = adapt_param_specs_from_search(response.search_data)
    assert "organism" in specs, "No organism param in GenesByTaxon"
    return specs


# ---------------------------------------------------------------------------
# flatten_vocab: must include parent AND leaf nodes
# ---------------------------------------------------------------------------


class TestFlattenVocabIncludesParentsVcr:
    """flatten_vocab returns both parent and leaf nodes from tree vocabs."""

    @pytest.mark.vcr
    async def test_leaf_organism_in_flattened(self, wdk_api: StrategyAPI) -> None:
        vocab = await discover_organism_vocab(wdk_api)
        leaf = await discover_leaf_organism(wdk_api)
        entries = flatten_vocab(vocab, prefer_term=True)
        values = {e.get("value") for e in entries}
        assert leaf in values, f"Leaf '{leaf}' missing from flatten_vocab"

    @pytest.mark.vcr
    async def test_parent_organism_in_flattened(self, wdk_api: StrategyAPI) -> None:
        vocab = await discover_organism_vocab(wdk_api)
        parent = await discover_parent_organism(wdk_api)
        entries = flatten_vocab(vocab, prefer_term=True)
        values = {e.get("value") for e in entries}
        assert parent in values, f"Parent '{parent}' missing from flatten_vocab"

    @pytest.mark.vcr
    async def test_flattened_has_many_entries(self, wdk_api: StrategyAPI) -> None:
        vocab = await discover_organism_vocab(wdk_api)
        entries = flatten_vocab(vocab, prefer_term=True)
        assert len(entries) > 5, "Vocabulary should have many entries"


# ---------------------------------------------------------------------------
# match_vocab_value: must accept parent terms
# ---------------------------------------------------------------------------


class TestMatchVocabValueVcr:
    """match_vocab_value matches parent terms, not just leaves."""

    @pytest.mark.vcr
    async def test_match_leaf_organism(self, wdk_api: StrategyAPI) -> None:
        vocab = await discover_organism_vocab(wdk_api)
        leaf = await discover_leaf_organism(wdk_api)
        result = match_vocab_value(vocab=vocab, param_name="organism", value=leaf)
        assert result == leaf

    @pytest.mark.vcr
    async def test_match_parent_organism(self, wdk_api: StrategyAPI) -> None:
        vocab = await discover_organism_vocab(wdk_api)
        parent = await discover_parent_organism(wdk_api)
        result = match_vocab_value(vocab=vocab, param_name="organism", value=parent)
        assert result == parent

    @pytest.mark.vcr
    async def test_nonexistent_rejected(self, wdk_api: StrategyAPI) -> None:
        vocab = await discover_organism_vocab(wdk_api)
        with pytest.raises(ValidationError):
            match_vocab_value(
                vocab=vocab, param_name="organism", value="NotARealOrganism"
            )


# ---------------------------------------------------------------------------
# Canonicalizer: parent values expanded to leaves
# ---------------------------------------------------------------------------


class TestCanonicalizerExpandsParentsVcr:
    """Parent values expand to leaf descendants during canonicalization."""

    @pytest.mark.vcr
    async def test_leaf_passes_through(self, wdk_api: StrategyAPI) -> None:
        specs = await _get_organism_specs(wdk_api)
        leaf = await discover_leaf_organism(wdk_api)
        c = ParameterCanonicalizer(specs=specs)
        result = c.canonicalize({"organism": f'["{leaf}"]'})
        values = [str(v) for v in decode_values(result["organism"], "organism")]
        assert leaf in values

    @pytest.mark.vcr
    async def test_parent_expands_to_leaf_strains(self, wdk_api: StrategyAPI) -> None:
        specs = await _get_organism_specs(wdk_api)
        parent = await discover_parent_organism(wdk_api)
        c = ParameterCanonicalizer(specs=specs)
        result = c.canonicalize({"organism": f'["{parent}"]'})
        values = [str(v) for v in decode_values(result["organism"], "organism")]
        # Parent should expand to at least one leaf
        assert len(values) >= 1
        # Parent itself should NOT be in the expanded values
        assert parent not in values

    @pytest.mark.vcr
    async def test_mixed_parent_and_leaf_deduplicates(self, wdk_api: StrategyAPI) -> None:
        specs = await _get_organism_specs(wdk_api)
        parent = await discover_parent_organism(wdk_api)
        leaf = await discover_leaf_organism(wdk_api)
        c = ParameterCanonicalizer(specs=specs)
        result = c.canonicalize({"organism": f'["{parent}", "{leaf}"]'})
        values = [str(v) for v in decode_values(result["organism"], "organism")]
        # No duplicates
        assert len(values) == len(set(values))
