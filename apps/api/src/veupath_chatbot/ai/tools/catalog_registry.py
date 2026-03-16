"""Catalog tool methods (RAG + WDK combined lookups)."""

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.ai.tools.catalog_rag_tools import CatalogRagTools
from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.combined_result import combined_result
from veupath_chatbot.ai.tools.example_plans_rag_tools import ExamplePlansRagTools
from veupath_chatbot.ai.tools.query_validation import (
    record_type_query_error,
    search_query_error,
)
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.catalog.rag_search import RagSearchService


class CatalogToolsMixin:
    """Mixin providing catalog @ai_function methods.

    Classes using this mixin must provide:
    - site_id: str
    - catalog_tools: CatalogTools
    - catalog_rag_tools: CatalogRagTools
    - example_plans_rag_tools: ExamplePlansRagTools
    """

    site_id: str = ""
    catalog_tools: CatalogTools = cast("CatalogTools", cast(object, None))
    catalog_rag_tools: CatalogRagTools = cast("CatalogRagTools", cast(object, None))
    example_plans_rag_tools: ExamplePlansRagTools = cast(
        "ExamplePlansRagTools", cast(object, None)
    )

    @ai_function()
    async def list_sites(self) -> JSONObject:
        """List all available VEuPathDB sites."""
        sites = await self.catalog_tools.list_sites()
        return combined_result(
            rag=[],
            wdk=sites,
            rag_note="No RAG source for sites list.",
            wdk_note="Authoritative list of configured sites.",
        )

    @ai_function()
    async def get_record_types(
        self,
        query: Annotated[
            str | None,
            AIParam(
                desc="Optional semantic query. Must include 2+ specific keywords; one-word/vague queries are rejected."
            ),
        ] = None,
        limit: Annotated[int, AIParam(desc="Max number of results to return")] = 20,
    ) -> JSONObject:
        """Get available record types for the current site (returns both RAG and live WDK)."""
        q = (query or "").strip()
        err = record_type_query_error(q) if q else None
        if err is not None:
            return combined_result(
                rag=[],
                wdk=[],
                rag_note=f"Rejected vague query: {err.get('message')}",
                wdk_note="Skipped live WDK record types list to avoid large irrelevant output; refine the query.",
            )

        rag = await self.catalog_rag_tools.rag_get_record_types(q or None, limit)
        wdk = None if q else await self.catalog_tools.get_record_types(self.site_id)
        return combined_result(
            rag=rag,
            wdk=wdk,
            rag_note="Qdrant semantic retrieval (requires a specific multi-keyword query; results include score and are thresholded).",
            wdk_note=(
                "Live WDK record types list (authoritative)."
                if not q
                else "Suppressed for query-based call; use RAG results or call get_record_types(query=None) to list all."
            ),
        )

    @ai_function()
    async def get_record_type_details(
        self,
        record_type_id: Annotated[
            str,
            AIParam(
                desc="Record type id/urlSegment (e.g. 'gene'). Use this only when you need detailed fields like formats/attributes/tables."
            ),
        ],
    ) -> JSONObject:
        """Get full record-type details from RAG (Qdrant payload)."""
        rag = await self.catalog_rag_tools.rag_get_record_type_details(record_type_id)
        return combined_result(
            rag=rag,
            wdk=None,
            rag_note="Qdrant record-type payload for a specific id (includes formats/attributes/tables).",
            wdk_note="No live WDK record-type detail endpoint is exposed here; use get_record_types(query=None) for the authoritative list.",
        )

    @ai_function()
    async def list_searches(
        self,
        record_type: Annotated[str, AIParam(desc="Record type to list searches for")],
    ) -> JSONObject:
        """List available searches for a record type on the current site (returns both RAG and live WDK)."""
        wdk = await self.catalog_tools.list_searches(self.site_id, record_type)
        return combined_result(
            rag=[],
            wdk=wdk,
            rag_note="Not applicable: Qdrant retrieval is query-driven; use search_for_searches(query, record_type=...) for RAG.",
            wdk_note="Live WDK searches list for record type (authoritative).",
        )

    @ai_function()
    async def get_search_parameters(
        self,
        record_type: Annotated[str, AIParam(desc="Record type that owns the search")],
        search_name: Annotated[str, AIParam(desc="WDK search/question urlSegment")],
    ) -> JSONObject:
        """Get detailed parameter info for a search (returns both RAG and live WDK)."""
        rag = await self.catalog_rag_tools.rag_get_search_metadata(
            record_type, search_name
        )
        wdk = await self.catalog_tools.get_search_parameters(
            self.site_id, record_type, search_name
        )
        return combined_result(
            rag=rag,
            wdk=wdk,
            rag_note="Qdrant cached search metadata (may be stale / incomplete if ingestion failed).",
            wdk_note="Live WDK expanded search details (authoritative when it succeeds).",
        )

    @ai_function()
    async def search_for_searches(
        self,
        query: Annotated[
            str,
            AIParam(
                desc="Semantic query to find relevant searches. Must include 2+ specific keywords; one-word/vague queries are rejected."
            ),
        ],
        record_type: Annotated[
            str | None, AIParam(desc="Optional record type to restrict the search")
        ] = None,
        limit: Annotated[int, AIParam(desc="Max number of results to return")] = 20,
    ) -> JSONObject:
        """Find searches matching a query term (returns both RAG and live WDK)."""
        err = search_query_error(query)
        if err is not None:
            return combined_result(
                rag=[],
                wdk=[],
                rag_note=f"Rejected vague query: {err.get('message')}",
                wdk_note="Skipped live WDK search to avoid large irrelevant output; refine the query.",
            )
        rag = await self.catalog_rag_tools.rag_search_for_searches(
            query, record_type, limit
        )
        wdk = await self.catalog_tools.search_for_searches(self.site_id, query)
        return combined_result(
            rag=rag,
            wdk=wdk,
            rag_note="Qdrant semantic retrieval (fast, may be stale; results include score and are thresholded).",
            wdk_note="Live WDK-backed keyword-ish search across catalog (authoritative).",
        )

    @ai_function()
    async def get_dependent_vocab(
        self,
        record_type: Annotated[str, AIParam(desc="Record type")],
        search_name: Annotated[str, AIParam(desc="Search name")],
        param_name: Annotated[str, AIParam(desc="Dependent parameter name to refresh")],
        context_values: Annotated[
            JSONObject | None,
            AIParam(desc="Current contextParamValues (paramName -> value)"),
        ] = None,
    ) -> JSONObject:
        """Get dependent vocab for a parameter.

        .. note::
           WDK's ``/refreshed-dependent-params`` requires a *changed* param value; if
           ``context_values`` does not include ``param_name``, we cannot call that
           endpoint safely (it will 422 for many params). In that case we fall back to
           fetching expanded search details and returning the parameter spec (which
           often includes the vocabulary needed to pick an initial value).
        """

        async def _fallback_from_search_details() -> JSONObject | None:
            rag_svc = RagSearchService(site_id=self.site_id)
            details = await rag_svc.get_search_details(
                record_type, search_name, expand_params=True
            )
            from veupath_chatbot.domain.parameters.specs import unwrap_search_data

            search_data = unwrap_search_data(details) or details
            params = (
                search_data.get("parameters") if isinstance(search_data, dict) else None
            )
            param_spec = None
            if isinstance(params, list):
                param_spec = next(
                    (
                        p
                        for p in params
                        if isinstance(p, dict) and p.get("name") == param_name
                    ),
                    None,
                )
            return {
                "source": "search_details",
                "searchName": search_name,
                "recordType": record_type,
                "paramName": param_name,
                "paramSpec": param_spec,
            }

        ctx = context_values or {}
        changed_value = ctx.get(param_name)
        if changed_value is None or changed_value == "":
            wdk_fallback = await _fallback_from_search_details()
            return combined_result(
                rag=None,
                wdk=wdk_fallback,
                rag_note="Skipped dependent vocab cache: missing changed param value in context_values.",
                wdk_note="Fetched expanded search details and extracted the requested param spec (often contains vocabulary).",
            )

        try:
            res = await self.catalog_rag_tools.rag_get_dependent_vocab(
                record_type, search_name, param_name, context_values
            )
            wdk_resp = res.get("wdkResponse") if isinstance(res, dict) else None
            return combined_result(
                rag=res,
                wdk=wdk_resp,
                rag_note="Qdrant-backed cache keyed by context hash; will call WDK on cache miss.",
                wdk_note="Authoritative WDK response (same payload as rag.wdkResponse).",
            )
        except Exception as exc:
            wdk_fallback = await _fallback_from_search_details()
            return combined_result(
                rag={"error": "dependent_vocab_failed", "detail": str(exc)},
                wdk=wdk_fallback,
                rag_note="Dependent vocab lookup failed; returning error payload.",
                wdk_note="Fallback: expanded search details param spec.",
            )

    @ai_function()
    async def search_example_plans(
        self,
        query: Annotated[
            str, AIParam(desc="User goal / query to match against example plans")
        ],
        limit: Annotated[int, AIParam(desc="Max number of results to return")] = 5,
    ) -> JSONObject:
        """Retrieve relevant public example plans (returns both RAG and live WDK availability note)."""
        rag = await self.example_plans_rag_tools.rag_search_example_plans(query, limit)
        return combined_result(
            rag=rag,
            wdk=None,
            rag_note="Qdrant semantic retrieval over ingested public strategies (includes full stepTree/steps).",
            wdk_note="No live WDK query endpoint exists for 'searching' public strategies; only list-all is available.",
        )
