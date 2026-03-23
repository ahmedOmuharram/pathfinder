"""AI tools for exporting data as downloadable files."""

from typing import Annotated, Literal, cast
from uuid import UUID

from kani import AIParam, ai_function

from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.export import get_export_service
from veupath_chatbot.services.gene_sets.store import get_gene_set_store


class ExportResultResponse(CamelModel):
    """Typed response for a successful gene-set export."""

    download_url: str
    filename: str
    format: str
    item_count: int
    expires_in_seconds: int


class GeneSetSummaryItem(CamelModel):
    """Summary of a single gene set for error context."""

    id: str
    name: str
    gene_count: int


class ExportToolsMixin:
    """Kani tool mixin for exporting data as downloadable files."""

    site_id: str = ""
    user_id: UUID | None = None

    def _available_gene_sets(self) -> list[JSONObject]:
        """Return summary of available gene sets for error messages."""
        store = get_gene_set_store()
        if self.user_id is not None:
            sets = store.list_for_user(self.user_id, site_id=self.site_id)
        else:
            sets = store.list_all(site_id=self.site_id)
        return [
            GeneSetSummaryItem(
                id=gs.id, name=gs.name, gene_count=len(gs.gene_ids)
            ).model_dump(by_alias=True, exclude_none=True, mode="json")
            for gs in sets[:10]
        ]

    @ai_function()
    async def export_gene_set(
        self,
        gene_set_id: Annotated[str, AIParam(desc="PathFinder gene set ID")],
        *,
        output_format: Annotated[
            str,
            AIParam(desc="Export format: csv or txt"),
        ] = "csv",
    ) -> JSONObject:
        """Export a gene set as a downloadable CSV or TXT file.

        Returns a download URL that the user can click to download the file.
        The URL expires after 10 minutes.
        """
        if output_format not in ("csv", "txt"):
            return tool_error(
                ErrorCode.VALIDATION_ERROR,
                "format must be 'csv' or 'txt'.",
                format=output_format,
            )

        store = get_gene_set_store()
        gs = await store.aget(gene_set_id)
        if gs is None:
            available = self._available_gene_sets()
            return tool_error(
                ErrorCode.NOT_FOUND,
                f"Gene set not found: {gene_set_id}. Use one of the available IDs below.",
                gene_set_id=gene_set_id,
                availableGeneSets=cast("JSONValue", available),
            )

        svc = get_export_service()
        fmt: Literal["csv", "txt"] = "txt" if output_format == "txt" else "csv"
        result = await svc.export_gene_set(gs, fmt)
        return ExportResultResponse(
            download_url=result.url,
            filename=result.filename,
            format=output_format,
            item_count=len(gs.gene_ids),
            expires_in_seconds=result.expires_in_seconds,
        ).model_dump(by_alias=True, exclude_none=True, mode="json")
