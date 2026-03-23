"""Tests for ExportService."""

import base64
import csv
import io
import json
from unittest.mock import AsyncMock

import pytest

from veupath_chatbot.services.enrichment.types import (
    EnrichmentResult,
    EnrichmentTerm,
)
from veupath_chatbot.services.experiment.types import Experiment, ExperimentConfig
from veupath_chatbot.services.experiment.types.metrics import GeneInfo
from veupath_chatbot.services.export.service import ExportService, _sanitize_filename
from veupath_chatbot.services.gene_sets.types import GeneSet


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.set = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    return redis


@pytest.fixture
def service(mock_redis: AsyncMock) -> ExportService:
    return ExportService(mock_redis)


def _make_gene_set(gene_ids: list[str] | None = None, name: str = "TestSet") -> GeneSet:
    return GeneSet(
        id="gs-1",
        name=name,
        site_id="PlasmoDB",
        gene_ids=gene_ids
        if gene_ids is not None
        else ["PF3D7_0100100", "PF3D7_0100200"],
        source="paste",
    )


def _make_enrichment() -> list[EnrichmentResult]:
    return [
        EnrichmentResult(
            analysis_type="go_process",
            terms=[
                EnrichmentTerm(
                    term_id="GO:0006412",
                    term_name="translation",
                    gene_count=15,
                    background_count=500,
                    fold_enrichment=2.5,
                    odds_ratio=3.0,
                    p_value=0.001,
                    fdr=0.01,
                    bonferroni=0.05,
                    genes=["PF3D7_0100100", "PF3D7_0100200"],
                ),
            ],
            total_genes_analyzed=100,
            background_size=5000,
        ),
    ]


def _make_experiment() -> Experiment:
    return Experiment(
        id="exp-1",
        config=ExperimentConfig(
            site_id="PlasmoDB",
            record_type="transcript",
            search_name="GenesByTaxon",
            parameters={"organism": "Plasmodium falciparum 3D7"},
            positive_controls=["PF3D7_0100100"],
            negative_controls=["PF3D7_0200100"],
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            name="TestExperiment",
        ),
        true_positive_genes=[
            GeneInfo(
                id="PF3D7_0100100",
                name="AP2-G",
                organism="P. falciparum",
                product="transcription factor",
            ),
        ],
        false_positive_genes=[
            GeneInfo(id="PF3D7_0300100", name="unknown", organism="P. falciparum"),
        ],
        false_negative_genes=[
            GeneInfo(id="PF3D7_0400100"),
        ],
        true_negative_genes=[
            GeneInfo(
                id="PF3D7_0200100",
                name="MSP1",
                organism="P. falciparum",
                product="merozoite surface protein",
            ),
        ],
    )


def _extract_stored_content(mock_redis: AsyncMock) -> str:
    """Helper to extract the file content from what was stored in Redis."""
    call_args = mock_redis.set.call_args
    stored_bytes = call_args[0][1]
    payload = json.loads(stored_bytes)
    return base64.b64decode(payload["data"]).decode("utf-8")


class TestSanitizeFilename:
    def test_strips_special_chars(self) -> None:
        assert _sanitize_filename("My Gene Set!@#") == "My_Gene_Set___"

    def test_truncates_long_names(self) -> None:
        assert len(_sanitize_filename("a" * 100)) == 60

    def test_preserves_valid_chars(self) -> None:
        assert _sanitize_filename("valid-name_123") == "valid-name_123"


class TestExportGeneSetCSV:
    @pytest.mark.anyio
    async def test_csv_has_header_and_rows(self, service: ExportService) -> None:
        gs = _make_gene_set()
        result = await service.export_gene_set(gs, "csv")
        assert result.filename == "TestSet.csv"
        assert result.content_type == "text/csv"
        assert result.size_bytes > 0
        assert result.url.startswith("/api/v1/exports/")
        assert result.expires_in_seconds == 600

    @pytest.mark.anyio
    async def test_csv_content_correct(
        self, service: ExportService, mock_redis: AsyncMock
    ) -> None:
        gs = _make_gene_set()
        await service.export_gene_set(gs, "csv")
        content = _extract_stored_content(mock_redis)
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        assert rows[0] == ["gene_id"]
        assert rows[1] == ["PF3D7_0100100"]
        assert rows[2] == ["PF3D7_0100200"]
        assert len(rows) == 3


class TestExportGeneSetTXT:
    @pytest.mark.anyio
    async def test_txt_has_one_id_per_line(
        self, service: ExportService, mock_redis: AsyncMock
    ) -> None:
        gs = _make_gene_set()
        result = await service.export_gene_set(gs, "txt")
        assert result.filename == "TestSet.txt"
        assert result.content_type == "text/plain"
        content = _extract_stored_content(mock_redis)
        assert content == "PF3D7_0100100\nPF3D7_0100200"

    @pytest.mark.anyio
    async def test_empty_gene_set(self, service: ExportService) -> None:
        gs = _make_gene_set(gene_ids=[])
        result = await service.export_gene_set(gs, "txt")
        assert result.size_bytes == 0


class TestExportEnrichment:
    @pytest.mark.anyio
    async def test_enrichment_csv_header(
        self, service: ExportService, mock_redis: AsyncMock
    ) -> None:
        results = _make_enrichment()
        export = await service.export_enrichment(results, "MyExperiment")
        assert export.filename == "MyExperiment_enrichment.csv"
        assert export.content_type == "text/csv"

        content = _extract_stored_content(mock_redis)
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        assert rows[0] == [
            "analysis_type",
            "term_id",
            "term_name",
            "gene_count",
            "background_count",
            "fold_enrichment",
            "odds_ratio",
            "p_value",
            "fdr",
            "bonferroni",
            "genes",
        ]
        assert rows[1][0] == "go_process"
        assert rows[1][1] == "GO:0006412"
        assert rows[1][10] == "PF3D7_0100100;PF3D7_0100200"

    @pytest.mark.anyio
    async def test_empty_enrichment(self, service: ExportService) -> None:
        export = await service.export_enrichment([], "empty")
        assert export.size_bytes > 0


class TestExportExperimentCSV:
    @pytest.mark.anyio
    async def test_csv_columns_and_classifications(
        self, service: ExportService, mock_redis: AsyncMock
    ) -> None:
        exp = _make_experiment()
        export = await service.export_experiment_results(exp, "csv")
        assert export.filename == "TestExperiment_results.csv"
        assert export.content_type == "text/csv"

        content = _extract_stored_content(mock_redis)
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        assert rows[0] == [
            "gene_id",
            "gene_name",
            "organism",
            "product",
            "classification",
        ]
        assert len(rows) == 5
        classifications = [r[4] for r in rows[1:]]
        assert classifications == ["TP", "FP", "FN", "TN"]

    @pytest.mark.anyio
    async def test_tsv_format(
        self, service: ExportService, mock_redis: AsyncMock
    ) -> None:
        exp = _make_experiment()
        export = await service.export_experiment_results(exp, "tsv")
        assert export.filename == "TestExperiment_results.tsv"
        assert export.content_type == "text/tab-separated-values"

    @pytest.mark.anyio
    async def test_empty_categories(self, service: ExportService) -> None:
        exp = Experiment(
            id="exp-2",
            config=ExperimentConfig(
                site_id="PlasmoDB",
                record_type="transcript",
                search_name="GenesByTaxon",
                parameters={},
                positive_controls=[],
                negative_controls=[],
                controls_search_name="GeneByLocusTag",
                controls_param_name="ds_gene_ids",
            ),
        )
        export = await service.export_experiment_results(exp, "csv")
        assert export.size_bytes > 0


class TestGetExport:
    @pytest.mark.anyio
    async def test_returns_none_for_missing(self, service: ExportService) -> None:
        result = await service.get_export("nonexistent")
        assert result is None

    @pytest.mark.anyio
    async def test_round_trip(
        self, service: ExportService, mock_redis: AsyncMock
    ) -> None:
        gs = _make_gene_set()
        await service.export_gene_set(gs, "csv")
        stored_value = mock_redis.set.call_args[0][1]

        mock_redis.get = AsyncMock(return_value=stored_value)
        result = await service.get_export("any-id")
        assert result is not None
        content, filename, content_type = result
        assert filename == "TestSet.csv"
        assert content_type == "text/csv"
        assert b"PF3D7_0100100" in content
