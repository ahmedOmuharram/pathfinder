"""Tests for ExportToolsMixin."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.ai.tools.export_tools import ExportToolsMixin
from veupath_chatbot.services.export.service import ExportResult
from veupath_chatbot.services.gene_sets.types import GeneSet


def _make_mixin() -> ExportToolsMixin:
    mixin = ExportToolsMixin()
    mixin.site_id = "PlasmoDB"
    mixin.user_id = None
    return mixin


def _make_export_result(**overrides: object) -> ExportResult:
    defaults = {
        "export_id": "abc-123",
        "filename": "test.csv",
        "content_type": "text/csv",
        "url": "/api/v1/exports/abc-123",
        "size_bytes": 42,
        "expires_in_seconds": 600,
    }
    defaults.update(overrides)
    return ExportResult(**defaults)


class TestExportGeneSetTool:
    @pytest.mark.anyio
    async def test_returns_download_url(self) -> None:
        mixin = _make_mixin()
        gs = GeneSet(
            id="gs-1",
            name="MyGenes",
            site_id="PlasmoDB",
            gene_ids=["PF3D7_0100100"],
            source="paste",
        )
        export_result = _make_export_result(filename="MyGenes.csv")

        with (
            patch(
                "veupath_chatbot.ai.tools.export_tools.get_gene_set_store"
            ) as mock_store_fn,
            patch(
                "veupath_chatbot.ai.tools.export_tools.get_export_service"
            ) as mock_svc_fn,
        ):
            store = MagicMock()
            store.aget = AsyncMock(return_value=gs)
            mock_store_fn.return_value = store

            svc = AsyncMock()
            svc.export_gene_set = AsyncMock(return_value=export_result)
            mock_svc_fn.return_value = svc

            result = await mixin.export_gene_set("gs-1", output_format="csv")

        assert result["downloadUrl"] == "/api/v1/exports/abc-123"
        assert result["filename"] == "MyGenes.csv"
        assert result["format"] == "csv"
        assert result["itemCount"] == 1

    @pytest.mark.anyio
    async def test_missing_gene_set_returns_error(self) -> None:
        mixin = _make_mixin()

        with patch(
            "veupath_chatbot.ai.tools.export_tools.get_gene_set_store"
        ) as mock_store_fn:
            store = MagicMock()
            store.aget = AsyncMock(return_value=None)
            mock_store_fn.return_value = store

            result = await mixin.export_gene_set("nonexistent", output_format="csv")

        assert result["ok"] is False
        assert "not found" in result["message"].lower()

    @pytest.mark.anyio
    async def test_invalid_format_returns_error(self) -> None:
        mixin = _make_mixin()
        result = await mixin.export_gene_set("gs-1", output_format="xml")
        assert result["ok"] is False
