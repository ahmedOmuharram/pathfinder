"""Agent tool registration mixins.

These methods expose lower-level tool objects (`CatalogTools`, `StrategyTools`, etc.)
as Kani `@ai_function()` methods on the agent.
"""

from __future__ import annotations


from typing import Annotated, Any

from kani import AIParam, ai_function

from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service


_VAGUE_RECORD_TYPE_TOKENS = {
    "gene",
    "genes",
    "transcript",
    "transcripts",
    "record",
    "records",
    "type",
    "types",
    "feature",
    "features",
}


def _tokenize_query(text: str) -> list[str]:
    import re

    return re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{2,}", (text or "").lower())


def _record_type_query_error(query: str) -> dict[str, Any] | None:
    """Return an error payload when query is too vague, else None."""
    q = (query or "").strip()
    if not q:
        return None
    tokens = _tokenize_query(q)
    if len(tokens) < 2:
        return {
            "error": "query_too_vague",
            "message": "get_record_types(query=...) requires 2+ specific keywords; one-word queries are rejected.",
            "query": q,
            "examples": [
                "gametocyte RNA-seq",
                "single cell atlas",
                "vector salivary gland",
                "metabolic pathway",
            ],
            "avoid": ["gene", "transcript", "record type"],
        }
    # Reject queries made only of generic tokens (e.g. "gene transcript").
    if all(t in _VAGUE_RECORD_TYPE_TOKENS for t in tokens):
        return {
            "error": "query_too_vague",
            "message": "Query is too generic; include at least one domain-specific keyword (not only 'gene'/'transcript').",
            "query": q,
            "tokens": tokens,
        }
    return None


def _search_query_error(query: str) -> dict[str, Any] | None:
    """Return an error payload when query is too vague, else None."""
    q = (query or "").strip()
    if not q:
        return {
            "error": "query_required",
            "message": "search_for_searches(query=...) requires a non-empty query.",
        }
    tokens = _tokenize_query(q)
    if len(tokens) < 2:
        return {
            "error": "query_too_vague",
            "message": "search_for_searches(query=...) requires 2+ specific keywords; one-word/vague queries are rejected.",
            "query": q,
            "examples": [
                "vector salivary gland",
                "gametocyte RNA-seq",
                "drug resistance markers",
                "liver stage expression",
            ],
        }
    return None


class AgentToolRegistryMixin:
    def _combined_result(
        self,
        *,
        rag: object,
        wdk: object,
        rag_note: str | None = None,
        wdk_note: str | None = None,
    ) -> dict:
        """Standardize combined (rag + wdk) tool outputs.

        This keeps the tool surface stable: callers always receive both data sources and can
        decide which to trust based on availability/staleness.
        """
        return {
            "rag": {"data": rag, "note": rag_note or ""},
            "wdk": {"data": wdk, "note": wdk_note or ""},
        }

    # Catalog tools
    @ai_function()
    async def list_sites(self):
        """List all available VEuPathDB sites."""
        sites = await self.catalog_tools.list_sites()
        # No RAG equivalent (sites list is local config / live).
        return self._combined_result(
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
    ):
        """Get available record types for the current site (returns both RAG and live WDK)."""
        q = (query or "").strip()
        err = _record_type_query_error(q) if q else None
        if err is not None:
            return self._combined_result(
                rag=[],
                wdk=[],
                rag_note=f"Rejected vague query: {err.get('message')}",
                wdk_note="Skipped live WDK record types list to avoid large irrelevant output; refine the query.",
            )

        rag = await self.catalog_rag_tools.rag_get_record_types(q or None, limit)
        # If caller provided a query, do not dump the full live list (can be large/noisy).
        wdk = None if q else await self.catalog_tools.get_record_types(self.site_id)
        return self._combined_result(
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
    ):
        """Get full record-type details from RAG (Qdrant payload)."""
        rag = await self.catalog_rag_tools.rag_get_record_type_details(record_type_id)
        return self._combined_result(
            rag=rag,
            wdk=None,
            rag_note="Qdrant record-type payload for a specific id (includes formats/attributes/tables).",
            wdk_note="No live WDK record-type detail endpoint is exposed here; use get_record_types(query=None) for the authoritative list.",
        )

    @ai_function()
    async def list_searches(
        self,
        record_type: Annotated[str, AIParam(desc="Record type to list searches for")],
    ):
        """List available searches for a record type on the current site (returns both RAG and live WDK)."""
        wdk = await self.catalog_tools.list_searches(self.site_id, record_type)
        # We do not provide a true "list all searches for record type" RAG API; Qdrant is query-driven.
        return self._combined_result(
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
    ):
        """Get detailed parameter info for a search (returns both RAG and live WDK)."""
        rag = await self.catalog_rag_tools.rag_get_search_metadata(record_type, search_name)
        wdk = await self.catalog_tools.get_search_parameters(
            self.site_id, record_type, search_name
        )
        return self._combined_result(
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
    ):
        """Find searches matching a query term (returns both RAG and live WDK)."""
        err = _search_query_error(query)
        if err is not None:
            return self._combined_result(
                rag=[],
                wdk=[],
                rag_note=f"Rejected vague query: {err.get('message')}",
                wdk_note="Skipped live WDK search to avoid large irrelevant output; refine the query.",
            )
        rag = await self.catalog_rag_tools.rag_search_for_searches(
            query, record_type, limit
        )
        wdk = await self.catalog_tools.search_for_searches(self.site_id, query)
        return self._combined_result(
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
            dict | None, AIParam(desc="Current contextParamValues (paramName -> value)")
        ] = None,
    ):
        """Get dependent vocab for a parameter.

        Notes:
        - WDK's `/refreshed-dependent-params` requires a *changed* param value; if `context_values`
          does not include `param_name`, we can't call that endpoint safely (it will 422 for many params).
        - In that case we fall back to fetching expanded search details and returning the parameter spec
          (which often includes the vocabulary needed to pick an initial value).
        """

        async def _fallback_from_search_details() -> dict[str, Any] | None:
            discovery = get_discovery_service()
            details = await discovery.get_search_details(
                self.site_id, record_type, search_name, expand_params=True
            )
            search_data = (
                details.get("searchData")
                if isinstance(details, dict) and isinstance(details.get("searchData"), dict)
                else details
            )
            params = (
                search_data.get("parameters")
                if isinstance(search_data, dict)
                else None
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
            return self._combined_result(
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
            return self._combined_result(
                rag=res,
                wdk=wdk_resp,
                rag_note="Qdrant-backed cache keyed by context hash; will call WDK on cache miss.",
                wdk_note="Authoritative WDK response (same payload as rag.wdkResponse).",
            )
        except Exception as exc:
            wdk_fallback = await _fallback_from_search_details()
            return self._combined_result(
                rag={"error": "dependent_vocab_failed", "detail": str(exc)},
                wdk=wdk_fallback,
                rag_note="Dependent vocab lookup failed; returning error payload.",
                wdk_note="Fallback: expanded search details param spec.",
            )

    @ai_function()
    async def search_example_plans(
        self,
        query: Annotated[str, AIParam(desc="User goal / query to match against example plans")],
        limit: Annotated[int, AIParam(desc="Max number of results to return")] = 5,
    ):
        """Retrieve relevant public example plans (returns both RAG and live WDK availability note)."""
        rag = await self.example_plans_rag_tools.rag_search_example_plans(query, limit)
        return self._combined_result(
            rag=rag,
            wdk=None,
            rag_note="Qdrant semantic retrieval over ingested public strategies (includes full stepTree/steps).",
            wdk_note="No live WDK query endpoint exists for 'searching' public strategies; only list-all is available.",
        )

    # Strategy tools
    @ai_function()
    async def create_step(
        self,
        search_name: Annotated[str | None, AIParam(desc="WDK search/question name")] = None,
        parameters: Annotated[
            dict | None, AIParam(desc="Parameter key/value mapping (values must be strings)")
        ] = None,
        record_type: Annotated[str | None, AIParam(desc="Record type context")] = None,
        primary_input_step_id: Annotated[
            str | None, AIParam(desc="Primary input step id (optional)")
        ] = None,
        secondary_input_step_id: Annotated[
            str | None, AIParam(desc="Secondary input step id (optional)")
        ] = None,
        operator: Annotated[
            str | None, AIParam(desc="Set operator for binary steps (e.g. UNION, INTERSECT, MINUS_LEFT)")
        ] = None,
        display_name: Annotated[str | None, AIParam(desc="Optional display name")] = None,
        upstream: Annotated[int | None, AIParam(desc="Upstream bp for COLOCATE")] = None,
        downstream: Annotated[int | None, AIParam(desc="Downstream bp for COLOCATE")] = None,
        strand: Annotated[
            str | None, AIParam(desc="Strand for COLOCATE: same|opposite|both")
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ):
        """Create a new strategy step (single step-construction API)."""
        return await self.strategy_tools.create_step(
            search_name=search_name,
            parameters=parameters,
            record_type=record_type,
            primary_input_step_id=primary_input_step_id,
            secondary_input_step_id=secondary_input_step_id,
            operator=operator,
            display_name=display_name,
            upstream=upstream,
            downstream=downstream,
            strand=strand,
            graph_id=graph_id,
        )

    @ai_function()
    async def explain_operator(
        self, operator: Annotated[str, AIParam(desc="Operator name to explain")]
    ):
        """Explain what a combine operator does."""
        return await self.strategy_tools.explain_operator(operator)

    @ai_function()
    async def list_current_steps(self):
        """List all steps in the current strategy context."""
        return await self.strategy_tools.list_current_steps()

    @ai_function()
    async def validate_graph_structure(self, graph_id: str | None = None):
        """Validate graph structure and single-output invariant."""
        return await self.strategy_tools.validate_graph_structure(graph_id)

    @ai_function()
    async def ensure_single_output(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to validate/repair")] = None,
        operator: Annotated[str, AIParam(desc="Combine operator to use when merging roots")] = "UNION",
        display_name: Annotated[str | None, AIParam(desc="Optional display name for final combine")] = None,
    ):
        """Ensure graph has a single output by combining roots (default UNION)."""
        return await self.strategy_tools.ensure_single_output(graph_id, operator, display_name)

    @ai_function()
    async def get_draft_step_counts(
        self, graph_id: Annotated[str | None, AIParam(desc="Graph ID to compute counts for")] = None
    ):
        """Compute draft step counts (WDK-backed) for local step IDs."""
        return await self.strategy_tools.get_draft_step_counts(graph_id)

    @ai_function()
    async def delete_step(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to delete")],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ):
        """Delete a step from the current graph."""
        return await self.strategy_tools.delete_step(step_id, graph_id)

    @ai_function()
    async def undo_last_change(
        self, graph_id: Annotated[str | None, AIParam(desc="Graph ID to undo changes in")] = None
    ):
        """Undo the last change to the current graph."""
        return await self.strategy_tools.undo_last_change(graph_id)

    @ai_function()
    async def rename_step(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to rename")],
        new_name: Annotated[str, AIParam(desc="New display name")],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ):
        """Rename a step's display name."""
        return await self.strategy_tools.rename_step(step_id, new_name, graph_id)

    @ai_function()
    async def update_step(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to update")],
        search_name: Annotated[str | None, AIParam(desc="Optional new search name")] = None,
        parameters: Annotated[
            dict | None, AIParam(desc="Optional new parameters object (values must be strings)")
        ] = None,
        operator: Annotated[str | None, AIParam(desc="Optional new operator")] = None,
        display_name: Annotated[str | None, AIParam(desc="Optional new display name")] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ):
        """Update an existing strategy step."""
        return await self.strategy_tools.update_step(
            step_id=step_id,
            search_name=search_name,
            parameters=parameters,
            operator=operator,
            display_name=display_name,
            graph_id=graph_id,
        )

    @ai_function()
    async def add_step_filter(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to attach the filter to")],
        filter_name: Annotated[str, AIParam(desc="Filter name")],
        value: Annotated[dict, AIParam(desc="Filter value object")],
        disabled: Annotated[bool, AIParam(desc="If true, attach filter disabled")] = False,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ):
        """Attach a filter to a step."""
        return await self.strategy_tools.add_step_filter(
            step_id, filter_name, value, disabled, graph_id
        )

    @ai_function()
    async def add_step_analysis(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to attach the analysis to")],
        analysis_type: Annotated[str, AIParam(desc="Analysis type identifier")],
        parameters: Annotated[
            dict | None, AIParam(desc="Analysis parameters mapping (values must be strings)")
        ] = None,
        custom_name: Annotated[str | None, AIParam(desc="Optional custom name for the analysis")] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ):
        """Attach an analysis configuration to a step."""
        return await self.strategy_tools.add_step_analysis(
            step_id, analysis_type, parameters, custom_name, graph_id
        )

    @ai_function()
    async def add_step_report(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to attach the report to")],
        report_name: Annotated[str, AIParam(desc="Report name (default: standard)")] = "standard",
        config: Annotated[dict | None, AIParam(desc="Optional report config object")] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ):
        """Attach a report configuration to a step."""
        return await self.strategy_tools.add_step_report(
            step_id, report_name, config, graph_id
        )

    # Execution tools
    @ai_function()
    async def build_strategy(
        self,
        strategy_name: Annotated[str | None, AIParam(desc="Optional strategy name")] = None,
        root_step_id: Annotated[str | None, AIParam(desc="Optional root step ID")] = None,
        record_type: Annotated[str | None, AIParam(desc="Optional record type")] = None,
        description: Annotated[str | None, AIParam(desc="Optional strategy description")] = None,
    ):
        """Build the current strategy on VEuPathDB."""
        return await self.execution_tools.build_strategy(
            strategy_name, root_step_id, record_type, description
        )

    @ai_function()
    async def preview_results(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to preview")],
        limit: Annotated[int, AIParam(desc="Max records to return")] = 10,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to use")] = None,
    ):
        """Preview results for a step (best-effort / may be simulated)."""
        return await self.execution_tools.preview_results(step_id, limit, graph_id)

    @ai_function()
    async def get_result_count(
        self, wdk_step_id: Annotated[int, AIParam(desc="WDK step id to count results for")]
    ):
        """Get the result count for a built step."""
        return await self.execution_tools.get_result_count(wdk_step_id)

    @ai_function()
    async def get_download_url(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step id to download")],
        format: Annotated[str, AIParam(desc="Download format (e.g. csv, tab, fasta)")] = "csv",
        attributes: Annotated[
            list[str] | None, AIParam(desc="Optional list of attribute names to include")
        ] = None,
    ):
        """Get a download URL for executed step results."""
        return await self.execution_tools.get_download_url(wdk_step_id, format, attributes)

    @ai_function()
    async def get_sample_records(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step id to sample records from")],
        limit: Annotated[int, AIParam(desc="Max records to return")] = 5,
    ):
        """Get sample records for an executed step."""
        return await self.execution_tools.get_sample_records(wdk_step_id, limit)

    # Conversation tools
    @ai_function()
    async def save_strategy(
        self,
        name: Annotated[str, AIParam(desc="Strategy name to save as")],
        description: Annotated[str | None, AIParam(desc="Optional description")] = None,
    ):
        """Save the current strategy for later use."""
        return await self.conversation_tools.save_strategy(name, description)

    @ai_function()
    async def rename_strategy(
        self,
        new_name: Annotated[str, AIParam(desc="New strategy name")],
        description: Annotated[str, AIParam(desc="New strategy description")],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to rename")] = None,
    ):
        """Rename the current strategy (name + description required)."""
        return await self.conversation_tools.rename_strategy(new_name, description, graph_id)

    @ai_function()
    async def clear_strategy(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to clear")] = None,
        confirm: Annotated[bool, AIParam(desc="Must be true to actually clear")] = False,
    ):
        """Clear all steps from a graph (requires confirm=true)."""
        return await self.conversation_tools.clear_strategy(graph_id, confirm)

    @ai_function()
    async def get_strategy_summary(self):
        """Get a summary of the current strategy."""
        return await self.conversation_tools.get_strategy_summary()

