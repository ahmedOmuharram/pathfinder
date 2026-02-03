"""Agent tool registration mixins.

These methods expose lower-level tool objects (`CatalogTools`, `StrategyTools`, etc.)
as Kani `@ai_function()` methods on the agent.
"""

from __future__ import annotations


from kani import ai_function


class AgentToolRegistryMixin:
    # Catalog tools
    @ai_function()
    async def list_sites(self):
        """List all available VEuPathDB sites."""
        return await self.catalog_tools.list_sites()

    @ai_function()
    async def get_record_types(self):
        """Get available record types for the current site."""
        return await self.catalog_tools.get_record_types(self.site_id)

    @ai_function()
    async def list_searches(self, record_type: str):
        """List available searches for a record type on the current site."""
        return await self.catalog_tools.list_searches(self.site_id, record_type)

    @ai_function()
    async def get_search_parameters(self, record_type: str, search_name: str):
        """Get detailed parameter information for a specific search."""
        return await self.catalog_tools.get_search_parameters(
            self.site_id, record_type, search_name
        )

    @ai_function()
    async def search_for_searches(self, record_type: str, query: str):
        """Find searches matching a query term."""
        return await self.catalog_tools.search_for_searches(
            self.site_id, record_type, query
        )

    # Strategy tools
    @ai_function()
    async def create_step(
        self,
        search_name: str | None = None,
        parameters: dict | None = None,
        record_type: str | None = None,
        primary_input_step_id: str | None = None,
        secondary_input_step_id: str | None = None,
        operator: str | None = None,
        display_name: str | None = None,
        upstream: int | None = None,
        downstream: int | None = None,
        strand: str | None = None,
        graph_id: str | None = None,
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
    async def explain_operator(self, operator: str):
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
        graph_id: str | None = None,
        operator: str = "UNION",
        display_name: str | None = None,
    ):
        """Ensure graph has a single output by combining roots (default UNION)."""
        return await self.strategy_tools.ensure_single_output(graph_id, operator, display_name)

    @ai_function()
    async def get_draft_step_counts(self, graph_id: str | None = None):
        """Compute draft step counts (WDK-backed) for local step IDs."""
        return await self.strategy_tools.get_draft_step_counts(graph_id)

    @ai_function()
    async def delete_step(self, step_id: str, graph_id: str | None = None):
        """Delete a step from the current graph."""
        return await self.strategy_tools.delete_step(step_id, graph_id)

    @ai_function()
    async def undo_last_change(self, graph_id: str | None = None):
        """Undo the last change to the current graph."""
        return await self.strategy_tools.undo_last_change(graph_id)

    @ai_function()
    async def rename_step(self, step_id: str, new_name: str, graph_id: str | None = None):
        """Rename a step's display name."""
        return await self.strategy_tools.rename_step(step_id, new_name, graph_id)

    @ai_function()
    async def update_step(
        self,
        step_id: str,
        search_name: str | None = None,
        parameters: dict | None = None,
        operator: str | None = None,
        display_name: str | None = None,
        graph_id: str | None = None,
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
        step_id: str,
        filter_name: str,
        value: dict,
        disabled: bool = False,
        graph_id: str | None = None,
    ):
        """Attach a filter to a step."""
        return await self.strategy_tools.add_step_filter(
            step_id, filter_name, value, disabled, graph_id
        )

    @ai_function()
    async def add_step_analysis(
        self,
        step_id: str,
        analysis_type: str,
        parameters: dict | None = None,
        custom_name: str | None = None,
        graph_id: str | None = None,
    ):
        """Attach an analysis configuration to a step."""
        return await self.strategy_tools.add_step_analysis(
            step_id, analysis_type, parameters, custom_name, graph_id
        )

    @ai_function()
    async def add_step_report(
        self,
        step_id: str,
        report_name: str = "standard",
        config: dict | None = None,
        graph_id: str | None = None,
    ):
        """Attach a report configuration to a step."""
        return await self.strategy_tools.add_step_report(
            step_id, report_name, config, graph_id
        )

    # Execution tools
    @ai_function()
    async def build_strategy(
        self,
        strategy_name: str | None = None,
        root_step_id: str | None = None,
        record_type: str | None = None,
        description: str | None = None,
    ):
        """Build the current strategy on VEuPathDB."""
        return await self.execution_tools.build_strategy(
            strategy_name, root_step_id, record_type, description
        )

    @ai_function()
    async def preview_results(self, step_id: str, limit: int = 10, graph_id: str | None = None):
        """Preview results for a step (best-effort / may be simulated)."""
        return await self.execution_tools.preview_results(step_id, limit, graph_id)

    @ai_function()
    async def get_result_count(self, wdk_step_id: int):
        """Get the result count for a built step."""
        return await self.execution_tools.get_result_count(wdk_step_id)

    @ai_function()
    async def get_download_url(
        self,
        wdk_step_id: int,
        format: str = "csv",
        attributes: list[str] | None = None,
    ):
        """Get a download URL for executed step results."""
        return await self.execution_tools.get_download_url(wdk_step_id, format, attributes)

    @ai_function()
    async def get_sample_records(self, wdk_step_id: int, limit: int = 5):
        """Get sample records for an executed step."""
        return await self.execution_tools.get_sample_records(wdk_step_id, limit)

    # Conversation tools
    @ai_function()
    async def save_strategy(self, name: str, description: str | None = None):
        """Save the current strategy for later use."""
        return await self.conversation_tools.save_strategy(name, description)

    @ai_function()
    async def rename_strategy(
        self,
        new_name: str,
        description: str,
        graph_id: str | None = None,
    ):
        """Rename the current strategy (name + description required)."""
        return await self.conversation_tools.rename_strategy(new_name, description, graph_id)

    @ai_function()
    async def clear_strategy(self, graph_id: str | None = None, confirm: bool = False):
        """Clear all steps from a graph (requires confirm=true)."""
        return await self.conversation_tools.clear_strategy(graph_id, confirm)

    @ai_function()
    async def get_strategy_summary(self):
        """Get a summary of the current strategy."""
        return await self.conversation_tools.get_strategy_summary()

