"""Public AI tool operations for strategy building.

This module composes the public `StrategyTools` class from smaller, purpose-driven
mixins to keep tool implementations easier to navigate.

``ensure_single_output`` lives here (not on a mixin) because it requires both
graph-inspection *and* step-creation capabilities.
"""

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.domain.strategy.session import StrategyGraph, StrategySession
from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.engine.base import StrategyToolsBase

from .attachment_ops import StrategyAttachmentOps
from .discovery_ops import StrategyDiscoveryOps
from .edit_ops import StrategyEditOps
from .graph_ops import GraphValidationResult, StrategyGraphOps
from .step_ops import StepInputSpec, StrategyStepOps


class StrategyTools(
    StrategyGraphOps,
    StrategyDiscoveryOps,
    StrategyStepOps,
    StrategyEditOps,
    StrategyAttachmentOps,
):
    """Tools for building search strategies.

    Composes tool methods from purpose-driven mixins. Methods that need
    capabilities from multiple mixins (e.g. ``ensure_single_output`` needs
    both graph inspection and step creation) live directly on this class.
    """

    def __init__(self, session: StrategySession) -> None:
        """Initialize StrategyTools with a session."""
        StrategyToolsBase.__init__(cast("StrategyToolsBase", self), session)

    @ai_function()
    async def ensure_single_output(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to repair")] = None,
        operator: Annotated[
            str,
            AIParam(
                desc=(
                    "Combine operator to merge orphan roots. Default INTERSECT "
                    "because most strategies are filter chains where each step "
                    "narrows the result. Use UNION only when you intentionally "
                    "want to broaden results (e.g., combining alternative "
                    "identification methods like text search + GO term)."
                )
            ),
        ] = "INTERSECT",
        display_name: Annotated[
            str | None, AIParam(desc="Optional display name for the final combine")
        ] = None,
    ) -> JSONObject:
        """Ensure the graph has exactly one output by combining orphan roots.

        If multiple roots exist, chains combines until one root remains.
        Default operator is INTERSECT (most strategies are filter chains).
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        validation = await self.validate_graph_structure(graph_id=graph.id)
        if validation.ok or len(validation.root_step_ids) <= 1:
            return _build_single_output_response(graph, validation)

        return await self._chain_combines(
            graph=graph,
            root_ids=validation.root_step_ids,
            operator=operator,
            display_name=display_name,
        )

    async def _chain_combines(
        self,
        *,
        graph: StrategyGraph,
        root_ids: list[str],
        operator: str,
        display_name: str | None,
    ) -> JSONObject:
        """Chain binary combines to reduce multiple roots to one."""
        current: str = root_ids[0]
        for index, next_id in enumerate(root_ids[1:], start=1):
            is_final = index == len(root_ids) - 1
            last_response = await self.create_step(
                inputs=StepInputSpec(
                    primary_input_step_id=current,
                    secondary_input_step_id=next_id,
                    operator=operator,
                    display_name=(display_name or "Combined output") if is_final else None,
                ),
                graph_id=graph.id,
            )
            if (
                not isinstance(last_response, dict)
                or last_response.get("ok") is False
                or last_response.get("error")
            ):
                return self._with_full_graph(
                    graph,
                    tool_error(
                        ErrorCode.ENSURE_SINGLE_OUTPUT_FAILED,
                        "Failed while combining roots to ensure a single output.",
                        operator=operator,
                        leftStepId=current,
                        rightStepId=next_id,
                        response=last_response,
                    ),
                )
            current = str(last_response.get("id") or current)

        final_validation = await self.validate_graph_structure(graph_id=graph.id)
        result: JSONObject = final_validation.model_dump(by_alias=True, exclude_none=True)
        return result


def _build_single_output_response(
    graph: StrategyGraph, validation: GraphValidationResult
) -> JSONObject:
    """Build response when graph already has a single output or no roots."""
    result: JSONObject = validation.model_dump(by_alias=True, exclude_none=True)
    if validation.root_step_ids:
        result["rootStepId"] = validation.root_step_ids[0]
    return result
