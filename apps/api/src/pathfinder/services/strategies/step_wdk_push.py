"""WDK push logic for step creation.

Best-effort push of newly created steps to the WDK backend. If the push
fails, the step still exists in the local graph and the sync service can
reconcile later.
"""

from pathfinder.domain.strategy.ast import PlanStepNode, walk_step_tree
from pathfinder.domain.strategy.ops import CombineOp, get_wdk_operator, parse_op
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.integrations.veupathdb.strategy_api import StrategyAPI
from pathfinder.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKSearchConfig,
    WDKValidation,
    encode_wdk_params,
)
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject

logger = get_logger(__name__)


async def _push_step_to_wdk(
    *,
    graph: StrategyGraph,
    step: PlanStepNode,
    site_id: str,
    search_name: str,
    parameters: JSONObject,
    parsed_op: CombineOp | None,
) -> tuple[int | None, WDKValidation | None, str | None]:
    """Push a newly created step to WDK and store its ID on the graph.

    Best-effort: if the push fails, the step still exists in the graph and
    the sync service can reconcile later.

    :returns: (wdk_step_id, wdk_validation, push_error) -- all None on success,
        push_error is set on failure with the reason WDK rejected the step.
    """
    wdk_step_id: int | None = None
    wdk_validation: WDKValidation | None = None
    push_error: str | None = None
    record_type = graph.record_type or "transcript"
    str_params: dict[str, str] = encode_wdk_params(parameters)
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
        push_error = str(exc)
        logger.warning(
            "WDK step push failed (non-fatal)",
            step_id=step.id,
            search_name=search_name,
            error=push_error,
        )

    return wdk_step_id, wdk_validation, push_error


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

    if parsed_op == CombineOp.COLOCATE:
        coloc = step.colocation_params
        if coloc is None:
            logger.warning("COLOCATE step missing colocation_params", step_id=step.id)
            return None
        # GenesBySpanLogic is a two-input search: span_a (primary) and
        # span_b (secondary) are AnswerParams auto-wired from the step
        # tree at strategy creation time.  create_transform_step blanks
        # all AnswerParams to ""; the step tree (built in sync.py) then
        # wires both primaryInput and secondaryInput to the correct
        # WDK step IDs.  secondary_wdk_id is intentionally unused here
        # — it is consumed by build_step_tree_from_graph.
        # GenesBySpanLogic always lives under "transcript", regardless of
        # the graph's record type (which may be "genomic-segment" from Set B).
        wdk_result = await api.create_transform_step(
            NewStepSpec(
                search_name="GenesBySpanLogic",
                search_config=WDKSearchConfig(parameters=coloc.to_wdk_params()),
                custom_name=step.display_name,
            ),
            input_step_id=primary_wdk_id,
            record_type="transcript",
        )
        return wdk_result.id

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


async def _update_existing_step(
    api: StrategyAPI,
    graph: StrategyGraph,
    step: PlanStepNode,
    site_id: str,
) -> None:
    """Update an existing WDK step's search-config (parameters + weight)."""
    wdk_step_id = graph.wdk_step_ids[step.id]
    kind = step.infer_kind()

    # Skip combine steps — their params are structural (empty strings)
    # and don't change.
    if kind == "combine":
        return

    record_type = graph.record_type or "transcript"
    str_params: dict[str, str] = encode_wdk_params(step.parameters)

    try:
        await api.update_step_search_config(
            step_id=wdk_step_id,
            search_config=WDKSearchConfig(parameters=str_params),
            record_type=record_type,
            search_name=step.search_name,
        )
    except (AppError, OSError) as exc:
        logger.warning(
            "WDK step update failed (non-fatal)",
            step_id=step.id,
            wdk_step_id=wdk_step_id,
            error=str(exc),
        )


async def push_all_steps_to_wdk(
    graph: StrategyGraph,
    site_id: str,
    *,
    update_existing: bool = False,
) -> list[str]:
    """Push all steps in a graph to WDK, bottom-up (leaves first).

    Skips steps that already have a WDK ID. Returns a list of step IDs
    that failed to push (non-fatal per step, but caller should check).
    """
    root_step = next(
        (graph.steps[sid] for sid in graph.roots if sid in graph.steps), None
    )
    if root_step is None:
        return []

    all_steps = walk_step_tree(root_step)
    failed: list[str] = []

    for step in all_steps:
        if step.id in graph.wdk_step_ids:
            if update_existing:
                if step.infer_kind() == "combine":
                    # Combine operators are creation-time params — can't update
                    # in-place. Evict the WDK ID to force recreation below.
                    del graph.wdk_step_ids[step.id]
                else:
                    api = get_strategy_api(site_id)
                    await _update_existing_step(api, graph, step, site_id)
                    continue
            else:
                continue

        parsed_op: CombineOp | None = None
        if step.operator is not None:
            try:
                parsed_op = parse_op(str(step.operator))
            except ValueError:
                parsed_op = None

        wdk_step_id, _validation, _push_error = await _push_step_to_wdk(
            graph=graph,
            step=step,
            site_id=site_id,
            search_name=step.search_name,
            parameters=dict(step.parameters),
            parsed_op=parsed_op,
        )
        if wdk_step_id is None:
            failed.append(step.id)

    return failed
