"""Strategy and conversation tool methods."""

from __future__ import annotations

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.ai.tools.conversation_tools import ConversationTools
from veupath_chatbot.ai.tools.execution_tools import ExecutionTools
from veupath_chatbot.ai.tools.result_tools import ResultTools
from veupath_chatbot.ai.tools.strategy_tools import StrategyTools
from veupath_chatbot.platform.types import JSONObject, JSONValue


class StrategyToolsMixin:
    """Mixin providing strategy, execution, and conversation @ai_function methods.

    Classes using this mixin must provide:
    - strategy_tools: StrategyTools
    - execution_tools: ExecutionTools
    - result_tools: ResultTools
    - conversation_tools: ConversationTools
    """

    strategy_tools: StrategyTools
    execution_tools: ExecutionTools
    result_tools: ResultTools
    conversation_tools: ConversationTools

    # Strategy tools
    @ai_function()
    async def create_step(
        self,
        search_name: Annotated[
            str | None, AIParam(desc="WDK search/question name")
        ] = None,
        parameters: Annotated[
            JSONObject | None,
            AIParam(desc="Parameter key/value mapping (values must be strings)"),
        ] = None,
        record_type: Annotated[str | None, AIParam(desc="Record type context")] = None,
        primary_input_step_id: Annotated[
            str | None, AIParam(desc="Primary input step id (optional)")
        ] = None,
        secondary_input_step_id: Annotated[
            str | None, AIParam(desc="Secondary input step id (optional)")
        ] = None,
        operator: Annotated[
            str | None,
            AIParam(
                desc="Set operator for binary steps (e.g. UNION, INTERSECT, MINUS)"
            ),
        ] = None,
        display_name: Annotated[
            str | None, AIParam(desc="Optional display name")
        ] = None,
        upstream: Annotated[
            int | None, AIParam(desc="Upstream bp for COLOCATE")
        ] = None,
        downstream: Annotated[
            int | None, AIParam(desc="Downstream bp for COLOCATE")
        ] = None,
        strand: Annotated[
            str | None, AIParam(desc="Strand for COLOCATE: same|opposite|both")
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Create a new strategy step. Inputs must reference current subtree roots (not internal nodes)."""
        result = await self.strategy_tools.create_step(
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
        return cast(JSONObject, result)

    @ai_function()
    async def explain_operator(
        self, operator: Annotated[str, AIParam(desc="Operator name to explain")]
    ) -> JSONObject:
        """Explain what a combine operator does."""
        result = await self.strategy_tools.explain_operator(operator)
        return cast(JSONObject, result)

    @ai_function()
    async def list_current_steps(self) -> JSONObject:
        """List all steps in the current strategy graph with WDK IDs and result counts."""
        result = await self.strategy_tools.list_current_steps()
        return cast(JSONObject, result)

    @ai_function()
    async def validate_graph_structure(self, graph_id: str | None = None) -> JSONObject:
        """Validate graph structure and single-output invariant."""
        result = await self.strategy_tools.validate_graph_structure(graph_id)
        return cast(JSONObject, result)

    @ai_function()
    async def ensure_single_output(
        self,
        graph_id: Annotated[
            str | None, AIParam(desc="Graph ID to validate/repair")
        ] = None,
        operator: Annotated[
            str, AIParam(desc="Combine operator to use when merging roots")
        ] = "UNION",
        display_name: Annotated[
            str | None, AIParam(desc="Optional display name for final combine")
        ] = None,
    ) -> JSONObject:
        """Ensure graph has a single output by combining roots (default UNION)."""
        result = await self.strategy_tools.ensure_single_output(
            graph_id, operator, display_name
        )
        return cast(JSONObject, result)

    @ai_function()
    async def delete_step(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to delete")],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Delete a step from the current graph."""
        delete_method = self.strategy_tools.delete_step
        result = await delete_method(step_id, graph_id)
        return cast(JSONObject, result)

    @ai_function()
    async def undo_last_change(
        self,
        graph_id: Annotated[
            str | None, AIParam(desc="Graph ID to undo changes in")
        ] = None,
    ) -> JSONObject:
        """Undo the last change to the current graph."""
        result = await self.strategy_tools.undo_last_change(graph_id)
        return cast(JSONObject, result)

    @ai_function()
    async def rename_step(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to rename")],
        new_name: Annotated[str, AIParam(desc="New display name")],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Rename a step's display name."""
        result = await self.strategy_tools.rename_step(step_id, new_name, graph_id)
        return cast(JSONObject, result)

    @ai_function()
    async def update_step(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to update")],
        search_name: Annotated[
            str | None, AIParam(desc="Optional new search name")
        ] = None,
        parameters: Annotated[
            JSONObject | None,
            AIParam(desc="Optional new parameters object (values must be strings)"),
        ] = None,
        operator: Annotated[str | None, AIParam(desc="Optional new operator")] = None,
        display_name: Annotated[
            str | None, AIParam(desc="Optional new display name")
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Update an existing strategy step."""
        result = await self.strategy_tools.update_step(
            step_id=step_id,
            search_name=search_name,
            parameters=parameters,
            operator=operator,
            display_name=display_name,
            graph_id=graph_id,
        )
        return cast(JSONObject, result)

    @ai_function()
    async def add_step_filter(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to attach the filter to")],
        filter_name: Annotated[str, AIParam(desc="Filter name")],
        value: Annotated[JSONValue, AIParam(desc="Filter value object")],
        disabled: Annotated[
            bool, AIParam(desc="If true, attach filter disabled")
        ] = False,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Attach a filter to a step."""
        filter_method = self.strategy_tools.add_step_filter
        result = await filter_method(step_id, filter_name, value, disabled, graph_id)
        return cast(JSONObject, result)

    @ai_function()
    async def add_step_analysis(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to attach the analysis to")],
        analysis_type: Annotated[str, AIParam(desc="Analysis type identifier")],
        parameters: Annotated[
            JSONObject | None,
            AIParam(desc="Analysis parameters mapping (values must be strings)"),
        ] = None,
        custom_name: Annotated[
            str | None, AIParam(desc="Optional custom name for the analysis")
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Attach an analysis configuration to a step."""
        analysis_method = self.strategy_tools.add_step_analysis
        result = await analysis_method(
            step_id, analysis_type, parameters, custom_name, graph_id
        )
        return cast(JSONObject, result)

    @ai_function()
    async def add_step_report(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to attach the report to")],
        report_name: Annotated[
            str, AIParam(desc="Report name (default: standard)")
        ] = "standard",
        config: Annotated[
            JSONObject | None, AIParam(desc="Optional report config object")
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Attach a report configuration to a step."""
        report_method = self.strategy_tools.add_step_report
        result = await report_method(step_id, report_name, config, graph_id)
        return cast(JSONObject, result)

    # Execution tools
    @ai_function()
    async def build_strategy(
        self,
        strategy_name: Annotated[
            str | None, AIParam(desc="Optional strategy name")
        ] = None,
        root_step_id: Annotated[
            str | None, AIParam(desc="Optional root step ID")
        ] = None,
        record_type: Annotated[str | None, AIParam(desc="Optional record type")] = None,
        description: Annotated[
            str | None, AIParam(desc="Optional strategy description")
        ] = None,
    ) -> JSONObject:
        """Build or update the current strategy as a draft on VEuPathDB (isSaved=false). Requires exactly 1 subtree root (or explicit root_step_id). Creates on first call, updates on subsequent calls. The user promotes drafts to saved via the UI."""
        result = await self.execution_tools.build_strategy(
            strategy_name, root_step_id, record_type, description
        )
        return cast(JSONObject, result)

    @ai_function()
    async def preview_results(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to preview")],
        limit: Annotated[int, AIParam(desc="Max records to return")] = 10,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to use")] = None,
    ) -> JSONObject:
        """Preview results for a step (best-effort / may be simulated)."""
        result = await self.execution_tools.preview_results(step_id, limit, graph_id)
        return cast(JSONObject, result)

    @ai_function()
    async def get_result_count(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step id to count results for")],
    ) -> JSONObject:
        """Get the result count for a built step."""
        result = await self.execution_tools.get_result_count(wdk_step_id)
        return cast(JSONObject, result)

    @ai_function()
    async def get_download_url(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step id to download")],
        format: Annotated[
            str, AIParam(desc="Download format (e.g. csv, tab, fasta)")
        ] = "csv",
        attributes: Annotated[
            list[str] | None,
            AIParam(desc="Optional list of attribute names to include"),
        ] = None,
    ) -> JSONObject:
        """Get a download URL for executed step results."""
        result = await self.result_tools.get_download_url(
            wdk_step_id, format, attributes
        )
        return cast(JSONObject, result)

    @ai_function()
    async def get_sample_records(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step id to sample records from")],
        limit: Annotated[int, AIParam(desc="Max records to return")] = 5,
    ) -> JSONObject:
        """Get sample records for an executed step."""
        result = await self.result_tools.get_sample_records(wdk_step_id, limit)
        return cast(JSONObject, result)

    # Conversation tools
    @ai_function()
    async def save_strategy(
        self,
        name: Annotated[str, AIParam(desc="Strategy name to save as")],
        description: Annotated[str | None, AIParam(desc="Optional description")] = None,
    ) -> JSONObject:
        """Save the current strategy for later use."""
        result = await self.conversation_tools.save_strategy(name, description)
        return cast(JSONObject, result)

    @ai_function()
    async def rename_strategy(
        self,
        new_name: Annotated[str, AIParam(desc="New strategy name")],
        description: Annotated[str, AIParam(desc="New strategy description")],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to rename")] = None,
    ) -> JSONObject:
        """Rename the current strategy (name + description required)."""
        result = await self.conversation_tools.rename_strategy(
            new_name, description, graph_id
        )
        return cast(JSONObject, result)

    @ai_function()
    async def clear_strategy(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to clear")] = None,
        confirm: Annotated[
            bool, AIParam(desc="Must be true to actually clear")
        ] = False,
    ) -> JSONObject:
        """Clear all steps from a graph (requires confirm=true)."""
        result = await self.conversation_tools.clear_strategy(graph_id, confirm)
        return cast(JSONObject, result)

    @ai_function()
    async def get_strategy_summary(self) -> JSONObject:
        """Get a summary of the current strategy."""
        result = await self.conversation_tools.get_strategy_summary()
        return cast(JSONObject, result)
