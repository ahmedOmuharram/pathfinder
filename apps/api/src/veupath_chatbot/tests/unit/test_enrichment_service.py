"""Tests for unified EnrichmentService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.services.experiment.types import EnrichmentResult
from veupath_chatbot.services.wdk.enrichment_service import EnrichmentService


class TestRunOnStep:
    @pytest.mark.asyncio
    async def test_delegates_to_run_on_step(self) -> None:
        with patch(
            "veupath_chatbot.services.wdk.enrichment_service.run_enrichment_on_step",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = MagicMock(analysis_type="go_process")
            svc = EnrichmentService()
            result = await svc.run(
                site_id="plasmodb",
                step_id=42,
                analysis_type="go_process",
            )
            mock_run.assert_called_once_with(
                site_id="plasmodb", step_id=42, analysis_type="go_process"
            )
            assert result.analysis_type == "go_process"

    @pytest.mark.asyncio
    async def test_step_id_takes_priority_over_search(self) -> None:
        """When both step_id and search_name are given, step_id wins."""
        with (
            patch(
                "veupath_chatbot.services.wdk.enrichment_service.run_enrichment_on_step",
                new_callable=AsyncMock,
            ) as mock_step,
            patch(
                "veupath_chatbot.services.wdk.enrichment_service.run_enrichment_analysis",
                new_callable=AsyncMock,
            ) as mock_search,
        ):
            mock_step.return_value = MagicMock(analysis_type="go_process")
            svc = EnrichmentService()
            await svc.run(
                site_id="plasmodb",
                step_id=42,
                analysis_type="go_process",
                search_name="GenesByText",
                record_type="gene",
                parameters={"text": "kinase"},
            )
            mock_step.assert_called_once()
            mock_search.assert_not_called()


class TestRunOnSearch:
    @pytest.mark.asyncio
    async def test_delegates_to_run_enrichment_analysis(self) -> None:
        with patch(
            "veupath_chatbot.services.wdk.enrichment_service.run_enrichment_analysis",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = MagicMock(analysis_type="pathway")
            svc = EnrichmentService()
            result = await svc.run(
                site_id="plasmodb",
                analysis_type="pathway",
                search_name="GenesByText",
                record_type="gene",
                parameters={"text": "kinase"},
            )
            mock_run.assert_called_once_with(
                site_id="plasmodb",
                record_type="gene",
                search_name="GenesByText",
                parameters={"text": "kinase"},
                analysis_type="pathway",
            )
            assert result.analysis_type == "pathway"

    @pytest.mark.asyncio
    async def test_defaults_record_type_to_gene(self) -> None:
        with patch(
            "veupath_chatbot.services.wdk.enrichment_service.run_enrichment_analysis",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = MagicMock(analysis_type="word")
            svc = EnrichmentService()
            await svc.run(
                site_id="plasmodb",
                analysis_type="word",
                search_name="GenesByText",
                parameters={"text": "kinase"},
            )
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["record_type"] == "transcript"

    @pytest.mark.asyncio
    async def test_raises_without_step_or_search(self) -> None:
        svc = EnrichmentService()
        with pytest.raises(ValueError, match="Either step_id or search_name"):
            await svc.run(site_id="plasmodb", analysis_type="go_process")


class TestRunBatch:
    @pytest.mark.asyncio
    async def test_runs_multiple_types(self) -> None:
        with (
            patch(
                "veupath_chatbot.services.wdk.enrichment_service.get_strategy_api",
                return_value=MagicMock(),
            ),
            patch(
                "veupath_chatbot.services.wdk.enrichment_service._execute_analysis",
                new_callable=AsyncMock,
            ) as mock_exec,
        ):
            mock_exec.side_effect = [
                EnrichmentResult(
                    analysis_type="go_process",
                    terms=[],
                    total_genes_analyzed=0,
                    background_size=0,
                ),
                EnrichmentResult(
                    analysis_type="pathway",
                    terms=[],
                    total_genes_analyzed=0,
                    background_size=0,
                ),
            ]
            svc = EnrichmentService()
            results, errors = await svc.run_batch(
                site_id="plasmodb",
                step_id=42,
                analysis_types=["go_process", "pathway"],
            )
            assert len(results) == 2
            assert len(errors) == 0
            assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_collects_errors_without_stopping(self) -> None:
        with (
            patch(
                "veupath_chatbot.services.wdk.enrichment_service.get_strategy_api",
                return_value=MagicMock(),
            ),
            patch(
                "veupath_chatbot.services.wdk.enrichment_service._execute_analysis",
                new_callable=AsyncMock,
            ) as mock_exec,
        ):
            mock_exec.side_effect = [
                EnrichmentResult(
                    analysis_type="go_process",
                    terms=[],
                    total_genes_analyzed=0,
                    background_size=0,
                ),
                RuntimeError("WDK timeout"),
                EnrichmentResult(
                    analysis_type="word",
                    terms=[],
                    total_genes_analyzed=0,
                    background_size=0,
                ),
            ]
            svc = EnrichmentService()
            results, errors = await svc.run_batch(
                site_id="plasmodb",
                step_id=42,
                analysis_types=["go_process", "pathway", "word"],
            )
            # All 3 types produce a result (errored one has error field set)
            assert len(results) == 3
            assert len(errors) == 1
            assert "pathway" in errors[0]
            # The failed result should carry the error message
            failed = [r for r in results if isinstance(r, EnrichmentResult) and r.error]
            assert len(failed) == 1
            assert failed[0].analysis_type == "pathway"

    @pytest.mark.asyncio
    async def test_empty_types_returns_empty(self) -> None:
        with patch(
            "veupath_chatbot.services.wdk.enrichment_service.get_strategy_api",
            return_value=MagicMock(),
        ):
            svc = EnrichmentService()
            results, errors = await svc.run_batch(
                site_id="plasmodb",
                step_id=42,
                analysis_types=[],
            )
            assert results == []
            assert errors == []
