"""Step creation tools (AI-exposed)."""

from typing import Annotated

from kani import AIParam, ai_function

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.engine.helpers import StrategyToolsHelpers
from veupath_chatbot.services.strategies.step_creation import create_step


class StrategyStepOps(StrategyToolsHelpers):
    """Tools that add new steps to a graph."""

    @ai_function()
    async def create_step(
        self,
        search_name: Annotated[
            str | None,
            AIParam(
                desc="WDK question/search name (required unless creating a binary step with operator)"
            ),
        ] = None,
        parameters: Annotated[
            JSONObject | None,
            AIParam(desc="WDK parameters as key-value pairs (optional)"),
        ] = None,
        record_type: Annotated[
            str | None,
            AIParam(
                desc="Record type context (e.g., 'transcript'). Defaults to 'transcript' which covers most VEuPathDB gene searches. If omitted, inferred from graph or discovery."
            ),
        ] = None,
        primary_input_step_id: Annotated[
            str | None, AIParam(desc="Primary input step id (optional)")
        ] = None,
        secondary_input_step_id: Annotated[
            str | None, AIParam(desc="Secondary input step id (optional)")
        ] = None,
        operator: Annotated[
            str | None,
            AIParam(
                desc="Set operator for binary steps (required if secondary_input_step_id is set)"
            ),
        ] = None,
        display_name: Annotated[
            str | None,
            AIParam(desc="Optional friendly name for this step"),
        ] = None,
        *,
        upstream: Annotated[
            int | None,
            AIParam(desc="Upstream bp for COLOCATE (default: 0)"),
        ] = None,
        downstream: Annotated[
            int | None,
            AIParam(desc="Downstream bp for COLOCATE (default: 0)"),
        ] = None,
        strand: Annotated[
            str | None,
            AIParam(desc="Strand for COLOCATE: same|opposite|both (default: both)"),
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Create a new strategy step.

        Step kind is inferred from structure:
        - leaf step: no inputs
        - unary step: primary_input_step_id only
        - binary step: primary + secondary input (+ operator)
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        result = await create_step(
            graph=graph,
            site_id=self.session.site_id,
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
            resolve_record_type_for_search=self._find_record_type_for_search,
            find_record_type_hint=self._find_record_type_hint,
            extract_vocab_options=self._extract_vocab_options,
            validation_error_payload=self._validation_error_payload,
        )

        if result.error is not None:
            return result.error

        if result.step is None:
            return self._graph_not_found(graph_id)

        response = self._serialize_step(graph, result.step)
        return self._with_full_graph(graph, response)
