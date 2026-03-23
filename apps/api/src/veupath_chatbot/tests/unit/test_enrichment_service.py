"""Tests for unified EnrichmentService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.services.enrichment.service import EnrichmentService
from veupath_chatbot.services.enrichment.types import EnrichmentResult

_MOCK_RESULT = EnrichmentResult(
    analysis_type="go_process",
    terms=[],
    total_genes_analyzed=0,
    background_size=0,
)


class TestRunOnStep:
    @pytest.mark.asyncio
    async def test_delegates_to_execute_analysis(self) -> None:
        svc = EnrichmentService()
        with (
            patch(
                "veupath_chatbot.services.enrichment.service.get_strategy_api",
                return_value=MagicMock(),
            ) as mock_api,
            patch.object(
                svc, "_execute_analysis", new_callable=AsyncMock
            ) as mock_exec,
        ):
            mock_exec.return_value = _MOCK_RESULT
            result = await svc.run(
                site_id="plasmodb",
                step_id=42,
                analysis_type="go_process",
            )
            mock_exec.assert_called_once_with(
                mock_api.return_value, 42, "go_process"
            )
            assert result.analysis_type == "go_process"

    @pytest.mark.asyncio
    async def test_step_id_takes_priority_over_search(self) -> None:
        """When both step_id and search_name are given, step_id wins."""
        svc = EnrichmentService()
        with (
            patch(
                "veupath_chatbot.services.enrichment.service.get_strategy_api",
                return_value=MagicMock(),
            ),
            patch.object(
                svc, "_execute_analysis", new_callable=AsyncMock
            ) as mock_exec,
        ):
            mock_exec.return_value = _MOCK_RESULT
            await svc.run(
                site_id="plasmodb",
                step_id=42,
                analysis_type="go_process",
                search_name="GenesByText",
                record_type="gene",
                parameters={"text": "kinase"},
            )
            # _execute_analysis called directly with step_id, no temp strategy
            mock_exec.assert_called_once()


class TestRunOnSearch:
    @pytest.mark.asyncio
    async def test_creates_temp_strategy(self) -> None:
        svc = EnrichmentService()
        mock_api = MagicMock()
        mock_api.create_step = AsyncMock(
            return_value=MagicMock(id=99)
        )
        mock_api.create_strategy = AsyncMock(
            return_value=MagicMock(id=200)
        )
        with (
            patch(
                "veupath_chatbot.services.enrichment.service.get_strategy_api",
                return_value=mock_api,
            ),
            patch(
                "veupath_chatbot.services.enrichment.service.delete_temp_strategy",
                new_callable=AsyncMock,
            ) as mock_delete,
            patch.object(
                svc, "_execute_analysis", new_callable=AsyncMock
            ) as mock_exec,
        ):
            mock_exec.return_value = EnrichmentResult(
                analysis_type="pathway",
                terms=[],
                total_genes_analyzed=0,
                background_size=0,
            )
            result = await svc.run(
                site_id="plasmodb",
                analysis_type="pathway",
                search_name="GenesByText",
                record_type="gene",
                parameters={"text": "kinase"},
            )
            mock_api.create_step.assert_called_once()
            mock_api.create_strategy.assert_called_once()
            mock_exec.assert_called_once_with(mock_api, 99, "pathway")
            mock_delete.assert_called_once_with(mock_api, 200)
            assert result.analysis_type == "pathway"

    @pytest.mark.asyncio
    async def test_defaults_record_type_to_transcript(self) -> None:
        svc = EnrichmentService()
        mock_api = MagicMock()
        mock_api.create_step = AsyncMock(return_value=MagicMock(id=99))
        mock_api.create_strategy = AsyncMock(return_value=MagicMock(id=200))
        with (
            patch(
                "veupath_chatbot.services.enrichment.service.get_strategy_api",
                return_value=mock_api,
            ),
            patch(
                "veupath_chatbot.services.enrichment.service.delete_temp_strategy",
                new_callable=AsyncMock,
            ),
            patch.object(
                svc, "_execute_analysis", new_callable=AsyncMock,
                return_value=_MOCK_RESULT,
            ),
        ):
            await svc.run(
                site_id="plasmodb",
                analysis_type="word",
                search_name="GenesByText",
                parameters={"text": "kinase"},
            )
            call_kwargs = mock_api.create_step.call_args
            assert call_kwargs[1]["record_type"] == "transcript"

    @pytest.mark.asyncio
    async def test_raises_without_step_or_search(self) -> None:
        svc = EnrichmentService()
        with pytest.raises(ValidationError, match="Either step_id or search_name"):
            await svc.run(site_id="plasmodb", analysis_type="go_process")


class TestRunBatch:
    @pytest.mark.asyncio
    async def test_runs_multiple_types(self) -> None:
        svc = EnrichmentService()
        with (
            patch(
                "veupath_chatbot.services.enrichment.service.get_strategy_api",
                return_value=MagicMock(),
            ),
            patch.object(
                svc, "_execute_analysis", new_callable=AsyncMock
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
        svc = EnrichmentService()
        with (
            patch(
                "veupath_chatbot.services.enrichment.service.get_strategy_api",
                return_value=MagicMock(),
            ),
            patch.object(
                svc, "_execute_analysis", new_callable=AsyncMock
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
        svc = EnrichmentService()
        with patch(
            "veupath_chatbot.services.enrichment.service.get_strategy_api",
            return_value=MagicMock(),
        ):
            results, errors = await svc.run_batch(
                site_id="plasmodb",
                step_id=42,
                analysis_types=[],
            )
            assert results == []
            assert errors == []
