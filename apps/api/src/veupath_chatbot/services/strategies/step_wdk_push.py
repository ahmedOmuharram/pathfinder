"""WDK push logic for step creation.

Best-effort push of newly created steps to the WDK backend. If the push
fails, the step still exists in the local graph and the sync service can
reconcile later.
"""

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp, get_wdk_operator
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKSearchConfig,
    WDKValidation,
)
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


async def _push_step_to_wdk(
    *,
    graph: StrategyGraph,
    step: PlanStepNode,
    site_id: str,
    search_name: str,
    parameters: JSONObject,
    parsed_op: CombineOp | None,
) -> tuple[int | None, WDKValidation | None]:
    """Push a newly created step to WDK and store its ID on the graph.

    Best-effort: if the push fails, the step still exists in the graph and
    the sync service can reconcile later.

    :returns: (wdk_step_id, wdk_validation) -- both None on failure.
    """
    wdk_step_id: int | None = None
    wdk_validation: WDKValidation | None = None
    record_type = graph.record_type or "transcript"
    str_params: dict[str, str] = {
        k: str(v) for k, v in parameters.items() if v is not None
    }

    try:
        api = get_strategy_api(site_id)
        is_binary = step.primary_input is not None and step.secondary_input is not None
        is_transform = step.primary_input is not None and not is_binary

        if is_binary:
            wdk_step_id = await _push_combine_step(
                api, graph, step, record_type, parsed_op
            )
        elif is_transform:
            wdk_step_id = await _push_transform_step(
                api, graph, step, search_name, str_params, record_type
            )
        else:
            wdk_step_id = await _push_leaf_step(
                api, search_name, str_params, step, record_type
            )

        if wdk_step_id is not None:
            graph.wdk_step_ids[step.id] = wdk_step_id
            try:
                wdk_step = await api.find_step(wdk_step_id)
                wdk_validation = wdk_step.validation
            except AppError, OSError:
                wdk_validation = None

    except (AppError, OSError) as exc:
        logger.warning(
            "WDK step push failed (non-fatal)",
            step_id=step.id,
            error=str(exc),
        )

    return wdk_step_id, wdk_validation


async def _push_leaf_step(
    api: StrategyAPI,
    search_name: str,
    str_params: dict[str, str],
    step: PlanStepNode,
    record_type: str,
) -> int:
    """Push a leaf step to WDK. Returns the WDK step ID."""
    wdk_result = await api.create_step(
        NewStepSpec(
            search_name=search_name,
            search_config=WDKSearchConfig(parameters=str_params),
            custom_name=step.display_name,
        ),
        record_type=record_type,
    )
    return wdk_result.id


async def _push_combine_step(
    api: StrategyAPI,
    graph: StrategyGraph,
    step: PlanStepNode,
    record_type: str,
    parsed_op: CombineOp | None,
) -> int | None:
    """Push a combine step to WDK.

    Returns the WDK step ID or None if inputs are missing.
    """
    primary_wdk_id = (
        graph.wdk_step_ids.get(step.primary_input.id) if step.primary_input else None
    )
    secondary_wdk_id = (
        graph.wdk_step_ids.get(step.secondary_input.id)
        if step.secondary_input
        else None
    )
    if primary_wdk_id is None or secondary_wdk_id is None or parsed_op is None:
        logger.warning(
            "Cannot push combine step: missing WDK input IDs or operator",
            step_id=step.id,
            primary_wdk_id=primary_wdk_id,
            secondary_wdk_id=secondary_wdk_id,
            operator=str(parsed_op),
        )
        return None

    wdk_result = await api.create_combined_step(
        primary_wdk_id,
        secondary_wdk_id,
        get_wdk_operator(parsed_op),
        record_type=record_type,
        spec_overrides=PatchStepSpec(custom_name=step.display_name)
        if step.display_name
        else None,
        wdk_weight=step.wdk_weight,
    )
    return wdk_result.id


async def _push_transform_step(
    api: StrategyAPI,
    graph: StrategyGraph,
    step: PlanStepNode,
    search_name: str,
    str_params: dict[str, str],
    record_type: str,
) -> int | None:
    """Push a transform step to WDK.

    Returns the WDK step ID or None if input is missing.
    """
    input_wdk_id = (
        graph.wdk_step_ids.get(step.primary_input.id) if step.primary_input else None
    )
    if input_wdk_id is None:
        logger.warning(
            "Cannot push transform step: missing WDK input ID",
            step_id=step.id,
        )
        return None

    wdk_result = await api.create_transform_step(
        NewStepSpec(
            search_name=search_name,
            search_config=WDKSearchConfig(parameters=str_params),
            custom_name=step.display_name,
        ),
        input_wdk_id,
        record_type=record_type,
    )
    return wdk_result.id
