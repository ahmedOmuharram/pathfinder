"""Lightweight AI assistant agent for the Experiment Lab wizard.

Uses the same Kani framework and research tools as the main agents but with
a much narrower scope: help the user navigate wizard steps (search selection,
parameter configuration, control gene discovery, run configuration).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from kani import AIParam, ChatMessage, ai_function
from kani.engines.base import BaseEngine

if TYPE_CHECKING:
    from veupath_chatbot.ai.stubs.kani import Kani
else:
    from kani import Kani

from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.research_registry import ResearchToolsMixin
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.gene_lookup import lookup_genes_by_text
from veupath_chatbot.services.research import (
    LiteratureSearchService,
    WebSearchService,
)


class ExperimentAssistantAgent(ResearchToolsMixin, Kani):
    """Scoped assistant for experiment wizard steps.

    Has access to:
    - Web search and literature search (via ``ResearchToolsMixin``)
    - VEuPathDB catalog tools (record types, searches, parameters)
    - Gene lookup (site-search based)
    """

    def __init__(
        self,
        engine: BaseEngine,
        site_id: str,
        system_prompt: str,
        chat_history: list[ChatMessage] | None = None,
    ) -> None:
        self.site_id = site_id
        self._catalog = CatalogTools()
        self.web_search_service = WebSearchService()
        self.literature_search_service = LiteratureSearchService()

        # stream_chat() accesses strategy_session.get_graph for tool result
        # processing; provide a no-op stub so it doesn't raise.
        self.strategy_session = type(
            "_Stub", (), {"get_graph": staticmethod(lambda: None)}
        )()

        super().__init__(
            engine=engine,
            system_prompt=system_prompt,
            chat_history=chat_history or [],
        )

    # -- Catalog tools (scoped to site) --------------------------------

    @ai_function()
    async def get_record_types(self) -> JSONObject:
        """List record types available on the current VEuPathDB site."""
        result = await self._catalog.get_record_types(self.site_id)
        return {"recordTypes": result}

    @ai_function()
    async def list_searches(
        self,
        record_type: Annotated[
            str, AIParam(desc="Record type (e.g. 'gene', 'transcript')")
        ],
    ) -> JSONObject:
        """List available WDK searches for a record type."""
        result = await self._catalog.list_searches(self.site_id, record_type)
        return {"searches": result}

    @ai_function()
    async def search_for_searches(
        self,
        query: Annotated[
            str, AIParam(desc="Free-text query to find relevant VEuPathDB searches")
        ],
    ) -> JSONObject:
        """Find VEuPathDB searches matching a research question or keyword."""
        result = await self._catalog.search_for_searches(self.site_id, query)
        return {"searches": result}

    @ai_function()
    async def get_search_parameters(
        self,
        record_type: Annotated[str, AIParam(desc="Record type")],
        search_name: Annotated[str, AIParam(desc="WDK search name")],
    ) -> JSONObject:
        """Get parameter specifications for a WDK search."""
        return await self._catalog.get_search_parameters(
            self.site_id, record_type, search_name
        )

    # -- Gene lookup ---------------------------------------------------

    @ai_function()
    async def lookup_genes(
        self,
        query: Annotated[
            str,
            AIParam(
                desc="Free-text query — gene name, symbol, locus tag, or description"
            ),
        ],
        organism: Annotated[
            str | None,
            AIParam(desc="Optional organism name to filter results"),
        ] = None,
        limit: Annotated[int, AIParam(desc="Max results to return (1-30)")] = 10,
    ) -> JSONObject:
        """Search for gene records on the current VEuPathDB site.

        Returns gene IDs, names, organisms, and product descriptions.
        Useful for resolving gene names from literature to VEuPathDB IDs
        that the user can add as controls.
        """
        return await lookup_genes_by_text(
            self.site_id,
            query,
            organism=organism,
            limit=min(limit, 30),
        )
