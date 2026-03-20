"""Live integration tests for tree vocabulary parameter handling.

Tests that PathFinder correctly handles parent and leaf organism values
against REAL VEuPathDB WDK API endpoints. Verifies:
- flatten_vocab includes parent AND leaf nodes
- match_vocab_value accepts parent terms
- Parent organism values can be submitted and expanded to leaves
- Cross-organism INTERSECT is rejected

Requires network access to plasmodb.org. Run with:

    pytest src/veupath_chatbot/tests/integration/test_live_tree_vocab.py -v -s

Skip with:

    pytest -m "not live_wdk"
"""

import pytest

from veupath_chatbot.domain.parameters._decode_values import decode_values
from veupath_chatbot.domain.parameters.canonicalize import ParameterCanonicalizer
from veupath_chatbot.domain.parameters.specs import (
    adapt_param_specs,
    unwrap_search_data,
)
from veupath_chatbot.domain.parameters.vocab_utils import (
    flatten_vocab,
    match_vocab_value,
)
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.organism import extract_output_organisms
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.platform.errors import ValidationError

pytestmark = pytest.mark.live_wdk

SITE = "plasmodb"
RECORD_TYPE = "transcript"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_organism_vocab(search_name: str = "GenesByTaxon") -> dict:
    """Fetch the organism parameter vocabulary from a real WDK search."""
    wdk = get_wdk_client(SITE)
    details = await wdk.get_search_details(RECORD_TYPE, search_name, expand_params=True)
    search_data = unwrap_search_data(details) or details
    params = search_data.get("parameters", [])
    for p in params:
        if isinstance(p, dict) and p.get("name") == "organism":
            return p.get("vocabulary", {})
    msg = f"No organism param found in {search_name}"
    raise AssertionError(msg)


async def _get_organism_spec(search_name: str = "GenesByTaxon") -> dict:
    """Fetch the full organism parameter spec."""
    wdk = get_wdk_client(SITE)
    details = await wdk.get_search_details(RECORD_TYPE, search_name, expand_params=True)
    search_data = unwrap_search_data(details) or details
    specs = adapt_param_specs(search_data)
    assert "organism" in specs, f"No organism param in {search_name}"
    return specs


# ---------------------------------------------------------------------------
# flatten_vocab: must include parent AND leaf nodes
# ---------------------------------------------------------------------------


class TestFlattenVocabIncludesParents:
    """flatten_vocab must return both parent and leaf nodes from tree vocabs."""

    async def test_plasmodium_falciparum_parent_in_flattened(self) -> None:
        vocab = await _get_organism_vocab()
        entries = flatten_vocab(vocab, prefer_term=True)
        values = {e.get("value") for e in entries}
        # "Plasmodium falciparum" is a parent (species level, has strain children)
        assert "Plasmodium falciparum" in values, (
            "Parent node 'Plasmodium falciparum' missing from flatten_vocab"
        )

    async def test_plasmodium_falciparum_3d7_leaf_in_flattened(self) -> None:
        vocab = await _get_organism_vocab()
        entries = flatten_vocab(vocab, prefer_term=True)
        values = {e.get("value") for e in entries}
        # "Plasmodium falciparum 3D7" is a leaf (specific strain)
        assert "Plasmodium falciparum 3D7" in values

    async def test_plasmodium_genus_parent_in_flattened(self) -> None:
        vocab = await _get_organism_vocab()
        entries = flatten_vocab(vocab, prefer_term=True)
        values = {e.get("value") for e in entries}
        # "Plasmodium" is a top-level genus parent
        assert "Plasmodium" in values, (
            "Genus parent 'Plasmodium' missing from flatten_vocab"
        )

    async def test_parent_count_less_than_total(self) -> None:
        """Sanity check: parents + leaves > old leaf-only count."""
        vocab = await _get_organism_vocab()
        entries = flatten_vocab(vocab, prefer_term=True)
        # Should have significantly more entries than just leaves
        # (PlasmoDB has ~20 leaf strains but also genus/species parents)
        assert len(entries) > 20


# ---------------------------------------------------------------------------
# match_vocab_value: must accept parent terms
# ---------------------------------------------------------------------------


class TestMatchVocabValueAcceptsParents:
    """match_vocab_value must match parent terms, not just leaves."""

    async def test_match_leaf_organism(self) -> None:
        vocab = await _get_organism_vocab()
        result = match_vocab_value(
            vocab=vocab, param_name="organism", value="Plasmodium falciparum 3D7"
        )
        assert result == "Plasmodium falciparum 3D7"

    async def test_match_parent_organism(self) -> None:
        """Parent term 'Plasmodium falciparum' should be accepted."""
        vocab = await _get_organism_vocab()
        result = match_vocab_value(
            vocab=vocab, param_name="organism", value="Plasmodium falciparum"
        )
        assert result == "Plasmodium falciparum"

    async def test_match_genus_parent(self) -> None:
        """Genus-level parent 'Plasmodium' should be accepted."""
        vocab = await _get_organism_vocab()
        result = match_vocab_value(
            vocab=vocab, param_name="organism", value="Plasmodium"
        )
        assert result == "Plasmodium"

    async def test_nonexistent_rejected(self) -> None:
        """A value not in the vocabulary at any level should be rejected."""
        vocab = await _get_organism_vocab()
        with pytest.raises(ValidationError):
            match_vocab_value(
                vocab=vocab, param_name="organism", value="NotARealOrganism"
            )


# ---------------------------------------------------------------------------
# Canonicalizer: parent values expanded to leaves
# ---------------------------------------------------------------------------


class TestCanonicalizerExpandsParents:
    """When count_only_leaves=True, parent values should expand to leaf descendants."""

    async def test_leaf_passes_through(self) -> None:
        specs = await _get_organism_spec()
        c = ParameterCanonicalizer(specs=specs)
        result = c.canonicalize({"organism": '["Plasmodium falciparum 3D7"]'})
        values = decode_values(result["organism"], "organism")
        assert "Plasmodium falciparum 3D7" in [str(v) for v in values]

    async def test_parent_expands_to_leaf_strains(self) -> None:
        """'Plasmodium falciparum' (species parent) should expand to all Pf strains."""
        specs = await _get_organism_spec()
        c = ParameterCanonicalizer(specs=specs)
        result = c.canonicalize({"organism": '["Plasmodium falciparum"]'})
        values = [str(v) for v in decode_values(result["organism"], "organism")]
        # Should include 3D7 and other strains, NOT "Plasmodium falciparum" itself
        assert "Plasmodium falciparum 3D7" in values
        assert "Plasmodium falciparum" not in values
        assert len(values) > 1  # Multiple strains

    async def test_mixed_parent_and_leaf_deduplicates(self) -> None:
        """Parent + one of its leaves should deduplicate."""
        specs = await _get_organism_spec()
        c = ParameterCanonicalizer(specs=specs)
        result = c.canonicalize(
            {"organism": '["Plasmodium falciparum", "Plasmodium falciparum 3D7"]'}
        )
        values = [str(v) for v in decode_values(result["organism"], "organism")]
        # 3D7 should appear once, not twice
        assert values.count("Plasmodium falciparum 3D7") == 1


# ---------------------------------------------------------------------------
# extract_output_organisms: works with real param formats
# ---------------------------------------------------------------------------


class TestExtractOutputOrganismsLive:
    """extract_output_organisms with realistic parameter shapes."""

    def test_single_organism_json_array(self) -> None:
        step = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        assert extract_output_organisms(step) == {"Plasmodium falciparum 3D7"}

    def test_multi_organism_json_array(self) -> None:
        step = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={
                "organism": '["Plasmodium falciparum 3D7", "Plasmodium vivax P01"]'
            },
        )
        result = extract_output_organisms(step)
        assert result == {"Plasmodium falciparum 3D7", "Plasmodium vivax P01"}

    def test_orthologs_overrides_inner_organism(self) -> None:
        inner = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        ortho = PlanStepNode(
            search_name="GenesByOrthologs",
            parameters={"organism": '["Plasmodium berghei ANKA"]'},
            primary_input=inner,
        )
        assert extract_output_organisms(ortho) == {"Plasmodium berghei ANKA"}

    def test_cross_species_intersect_detected(self) -> None:
        """The two inputs to an INTERSECT have disjoint organisms."""
        ortho = PlanStepNode(
            search_name="GenesByOrthologs",
            parameters={"organism": '["Plasmodium berghei ANKA"]'},
            primary_input=PlanStepNode(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            ),
        )
        pf_expr = PlanStepNode(
            search_name="GenesByRNASeqPercentile",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        orgs_a = extract_output_organisms(ortho)
        orgs_b = extract_output_organisms(pf_expr)
        assert orgs_a is not None
        assert orgs_b is not None
        assert orgs_a.isdisjoint(orgs_b), (
            f"Cross-species mismatch not detected: {orgs_a} vs {orgs_b}"
        )
