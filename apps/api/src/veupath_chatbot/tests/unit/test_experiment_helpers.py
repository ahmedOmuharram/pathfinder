"""Tests for experiment helper utilities.

Mocks: resolve_gene_ids is mocked (gene resolution service).
Tests verify enrichment merge logic and error fallback behavior.
"""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.experiment.helpers import (
    _enrich_list,
    extract_and_enrich_genes,
)
from veupath_chatbot.services.experiment.types import (
    ControlSetData,
    ControlTestResult,
    GeneInfo,
)
from veupath_chatbot.services.gene_lookup.result import GeneResult
from veupath_chatbot.services.gene_lookup.wdk import GeneResolveResult


class TestEnrichList:
    def test_enriches_genes_from_lookup(self) -> None:
        genes = [GeneInfo(id="PF3D7_1234"), GeneInfo(id="PF3D7_5678")]
        lookup = {
            "PF3D7_1234": GeneResult(
                gene_id="PF3D7_1234",
                gene_name="Gene A",
                organism="P. falciparum",
                product="kinase",
            ),
        }
        enriched = _enrich_list(genes, lookup)
        assert enriched[0].name == "Gene A"
        assert enriched[0].organism == "P. falciparum"
        assert enriched[0].product == "kinase"
        assert enriched[1].name is None
        assert enriched[1].product is None

    def test_preserves_order(self) -> None:
        genes = [GeneInfo(id="c"), GeneInfo(id="a"), GeneInfo(id="b")]
        enriched = _enrich_list(genes, {})
        assert [g.id for g in enriched] == ["c", "a", "b"]


class TestExtractAndEnrichGenes:
    async def test_extracts_and_enriches(self) -> None:
        result = ControlTestResult(
            positive=ControlSetData(
                intersection_ids=["g1", "g2"],
                missing_ids_sample=["g3"],
            ),
            negative=ControlSetData(
                intersection_ids=["g4"],
                missing_ids_sample=["g5"],
            ),
        )

        mock_resolve = AsyncMock(
            return_value=GeneResolveResult(
                records=[
                    GeneResult(
                        gene_id="g1",
                        gene_name="Gene1",
                        organism="Org1",
                        product="Prod1",
                    ),
                    GeneResult(
                        gene_id="g3",
                        gene_name="Gene3",
                        organism="Org3",
                        product="Prod3",
                    ),
                ],
                total_count=2,
            )
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

        assert [g.id for g in tp] == ["g1", "g2"]
        assert tp[0].product == "Prod1"
        assert tp[1].product is None

        assert [g.id for g in fn] == ["g3"]
        assert fn[0].product == "Prod3"

        assert [g.id for g in fp] == ["g4"]
        assert [g.id for g in tn] == ["g5"]

    async def test_enrichment_failure_returns_bare_genes(self) -> None:
        result = ControlTestResult(
            positive=ControlSetData(intersection_ids=["g1"]),
            negative=ControlSetData(intersection_ids=["g2"]),
        )

        mock_resolve = AsyncMock(side_effect=WDKError(detail="WDK down"))

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
        assert tp[0].product is None
