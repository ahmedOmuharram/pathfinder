"""Tests for experiment helper utilities."""

from unittest.mock import AsyncMock, patch

import pytest

from veupath_chatbot.services.experiment.helpers import (
    _enrich_list,
    _extract_gene_list,
    _extract_id_set,
    extract_and_enrich_genes,
)
from veupath_chatbot.services.experiment.types import GeneInfo

# ── _extract_gene_list ──


class TestExtractGeneList:
    def test_extracts_intersection_ids(self) -> None:
        result = {"positive": {"intersectionIds": ["g1", "g2", "g3"]}}
        genes = _extract_gene_list(result, "positive", "intersectionIds")
        assert [g.id for g in genes] == ["g1", "g2", "g3"]
        assert all(g.name is None for g in genes)

    def test_missing_section_returns_empty(self) -> None:
        assert _extract_gene_list({}, "positive", "intersectionIds") == []

    def test_fallback_from_controls(self) -> None:
        result = {"negative": {"intersectionIds": ["g1"]}}
        hit_ids = _extract_id_set(result, "negative", "intersectionIds")
        genes = _extract_gene_list(
            {},
            "negative",
            "missingIdsSample",
            fallback_from_controls=True,
            all_controls=["g1", "g2", "g3"],
            hit_ids=hit_ids,
        )
        # Should exclude g1 (in hit_ids) and include g2, g3
        assert [g.id for g in genes] == ["g2", "g3"]


# ── _enrich_list ──


class TestEnrichList:
    def test_enriches_genes_from_lookup(self) -> None:
        genes = [GeneInfo(id="PF3D7_1234"), GeneInfo(id="PF3D7_5678")]
        lookup = {
            "PF3D7_1234": {
                "geneId": "PF3D7_1234",
                "geneName": "Gene A",
                "organism": "P. falciparum",
                "product": "kinase",
            },
        }
        enriched = _enrich_list(genes, lookup)
        assert enriched[0].name == "Gene A"
        assert enriched[0].organism == "P. falciparum"
        assert enriched[0].product == "kinase"
        # Second gene not in lookup — stays bare
        assert enriched[1].name is None
        assert enriched[1].product is None

    def test_preserves_order(self) -> None:
        genes = [GeneInfo(id="c"), GeneInfo(id="a"), GeneInfo(id="b")]
        enriched = _enrich_list(genes, {})
        assert [g.id for g in enriched] == ["c", "a", "b"]


# ── extract_and_enrich_genes ──


class TestExtractAndEnrichGenes:
    @pytest.mark.asyncio
    async def test_extracts_and_enriches(self) -> None:
        """extract_and_enrich_genes should extract genes from result and enrich them."""
        result = {
            "positive": {
                "intersectionIds": ["g1", "g2"],
                "missingIdsSample": ["g3"],
            },
            "negative": {
                "intersectionIds": ["g4"],
                "missingIdsSample": ["g5"],
            },
        }

        mock_resolve = AsyncMock(
            return_value={
                "records": [
                    {
                        "geneId": "g1",
                        "geneName": "Gene1",
                        "organism": "Org1",
                        "product": "Prod1",
                    },
                    {
                        "geneId": "g3",
                        "geneName": "Gene3",
                        "organism": "Org3",
                        "product": "Prod3",
                    },
                ],
                "totalCount": 2,
            }
        )

        with patch(
            "veupath_chatbot.services.experiment.helpers.resolve_gene_ids",
            mock_resolve,
        ):
            tp, fn, fp, tn = await extract_and_enrich_genes(
                site_id="plasmodb",
                result=result,
                negative_controls=["g4", "g5", "g6"],
            )

        # True positives: g1, g2 (from positive.intersectionIds)
        assert [g.id for g in tp] == ["g1", "g2"]
        assert tp[0].product == "Prod1"  # enriched
        assert tp[1].product is None  # not in resolve response

        # False negatives: g3 (from positive.missingIdsSample)
        assert [g.id for g in fn] == ["g3"]
        assert fn[0].product == "Prod3"

        # False positives: g4 (from negative.intersectionIds)
        assert [g.id for g in fp] == ["g4"]

        # True negatives: g5 (from negative.missingIdsSample)
        assert [g.id for g in tn] == ["g5"]

        # All unique IDs sent to resolve
        call_args = mock_resolve.call_args
        assert set(call_args[1]["gene_ids"]) == {"g1", "g2", "g3", "g4", "g5"}

    @pytest.mark.asyncio
    async def test_enrichment_failure_returns_bare_genes(self) -> None:
        """If WDK enrichment fails, should still return extracted genes."""
        result = {
            "positive": {"intersectionIds": ["g1"]},
            "negative": {"intersectionIds": ["g2"]},
        }

        mock_resolve = AsyncMock(side_effect=Exception("WDK down"))

        with patch(
            "veupath_chatbot.services.experiment.helpers.resolve_gene_ids",
            mock_resolve,
        ):
            tp, _fn, _fp, _tn = await extract_and_enrich_genes(
                site_id="plasmodb",
                result=result,
                negative_controls=None,
            )

        assert [g.id for g in tp] == ["g1"]
        assert tp[0].product is None  # not enriched due to failure
