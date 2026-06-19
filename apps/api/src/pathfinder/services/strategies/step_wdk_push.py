"""WDK push logic for step creation.

Best-effort push of newly created steps to the WDK backend. If the push
fails, the step still exists in the local graph and the sync service can
reconcile later.
"""

from typing import assert_never

from pydantic import BaseModel, ConfigDict

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.ast import (
    COMBINE_SEARCH_NAME,
    StrategyStepNode,
    walk_step_tree,
)
from pathfinder.domain.strategy.ops import CombineOp, get_wdk_operator
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.integrations.veupathdb.strategy_api import StrategyAPI
from pathfinder.integrations.veupathdb.value_decoding import encode_params
from pathfinder.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKSearchConfig,
)
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.services.catalog.param_validation import (
    ValidationCallbacks,
    validate_parameters,
)
from pathfinder.services.catalog.validation_callbacks import make_validation_callbacks
from pathfinder.services.strategies.step_push_planner import (
    CreateAction,
    PatchAction,
    RecreateAction,
    SkipAction,
    StepPushPlan,
)
from pathfinder.services.strategies.sync_state import WDKSyncState


class PushOutcome(BaseModel):
    """Outcome of a `push_steps_with_plan` call.

    `succeeded` is the ordered list of step IDs whose CREATE/PATCH/RECREATE
    plan entry completed without error. `failed` is the ordered list of
    step IDs whose action raised. `partial` is True iff any step failed.
    """

    model_config = ConfigDict(frozen=True)
    succeeded: list[str]
    failed: list[str]

    @property
    def partial(self) -> bool:
        return len(self.failed) > 0


logger = get_logger(__name__)


async def push_step_to_wdk(
    *,
    sync_state: WDKSyncState,
    step: StrategyStepNode,
    site_id: str,
    record_type: str,
    search_name: str,
    parameters: dict[str, ParamValue],
) -> tuple[int | None, StepValidation | None, str | None]:
    """Push a newly created step to WDK and store its ID on sync_state.

    Best-effort: if the push fails, the step still exists in the graph and
    the sync service can reconcile later.

    :returns: (wdk_step_id, wdk_validation, push_error) -- all None on success,
        push_error is set on failure with the reason WDK rejected the step.
    """
    parsed_op: CombineOp | None = step.operator
    wdk_step_id: int | None = None
    wdk_validation: StepValidation | None = None
    push_error: str | None = None
    str_params: dict[str, str] = encode_params(parameters)
    try:
        api = get_strategy_api(site_id)
        is_binary = step.primary_input is not None and step.secondary_input is not None
        is_transform = step.primary_input is not None and not is_binary

        if is_binary:
            wdk_step_id = await _push_combine_step(
                api, sync_state, step, record_type, parsed_op
            )
        elif is_transform:
            wdk_step_id = await _push_transform_step(
                api, sync_state, step, search_name, str_params, record_type
            )
        else:
            wdk_step_id = await _push_leaf_step(
                api, search_name, str_params, step, record_type
            )

        if wdk_step_id is not None:
            sync_state.wdk_step_ids[step.id] = wdk_step_id
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
    step: StrategyStepNode,
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
    sync_state: WDKSyncState,
    step: StrategyStepNode,
    record_type: str,
    parsed_op: CombineOp | None,
) -> int | None:
    """Push a combine step to WDK.

    Returns the WDK step ID or None if inputs are missing.
    """
    primary_wdk_id = (
        sync_state.wdk_step_ids.get(step.primary_input.id)
        if step.primary_input
        else None
    )
    secondary_wdk_id = (
        sync_state.wdk_step_ids.get(step.secondary_input.id)
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
    if step.expanded_strategy_id is not None:
        # WDK's create-combined-step endpoint doesn't accept expanded; PATCH
        # immediately after creation so the saved-strategy reference renders
        # as a collapsed input on next reload.
        await api.update_step_properties(
            wdk_result.id,
            spec=PatchStepSpec(
                expanded=True,
                expanded_name=step.expanded_name,
            ),
        )
    return wdk_result.id


async def _push_transform_step(
    api: StrategyAPI,
    sync_state: WDKSyncState,
    step: StrategyStepNode,
    search_name: str,
    str_params: dict[str, str],
    record_type: str,
) -> int | None:
    """Push a transform step to WDK.

    Returns the WDK step ID or None if input is missing.
    """
    input_wdk_id = (
        sync_state.wdk_step_ids.get(step.primary_input.id)
        if step.primary_input
        else None
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
    sync_state: WDKSyncState,
    step: StrategyStepNode,
    record_type: str,
) -> None:
    """Update an existing WDK step's search-config (parameters + weight)."""
    wdk_step_id = sync_state.wdk_step_ids[step.id]
    kind = step.infer_kind()

    # Skip combine steps — their params are structural (empty strings)
    # and don't change.
    if kind == "combine":
        return
    str_params: dict[str, str] = encode_params(step.parameters)

    await api.update_step_search_config(
        step_id=wdk_step_id,
        search_config=WDKSearchConfig(parameters=str_params),
        record_type=record_type,
        search_name=step.search_name,
    )


async def _patch_combine_metadata(
    api: StrategyAPI,
    sync_state: WDKSyncState,
    step: StrategyStepNode,
) -> None:
    # WDK combine operators are creation-time params; only display name /
    # weight are PATCHable on a combine step.
    wdk_step_id = sync_state.wdk_step_ids[step.id]
    if step.display_name is None:
        return
    await api.update_step_properties(
        step_id=wdk_step_id,
        spec=PatchStepSpec(custom_name=step.display_name),
    )


async def _execute_patch(
    sync_state: WDKSyncState,
    site_id: str,
    step: StrategyStepNode,
    record_type: str,
) -> str | None:
    api = get_strategy_api(site_id)
    try:
        if step.infer_kind() == "combine":
            await _patch_combine_metadata(api, sync_state, step)
        else:
            await _update_existing_step(api, sync_state, step, record_type)
    except (AppError, OSError) as exc:
        msg = str(exc)
        sync_state.wdk_push_errors[step.id] = msg
        return msg
    return None


async def _execute_create(
    sync_state: WDKSyncState,
    site_id: str,
    step: StrategyStepNode,
    record_type: str,
) -> str | None:
    wdk_step_id, _validation, push_error = await push_step_to_wdk(
        sync_state=sync_state,
        step=step,
        site_id=site_id,
        record_type=record_type,
        search_name=step.search_name,
        parameters=step.parameters,
    )
    if wdk_step_id is None:
        if push_error:
            sync_state.wdk_push_errors[step.id] = push_error
        return push_error or "push returned no wdk step id"
    return None


async def _execute_recreate(
    sync_state: WDKSyncState,
    site_id: str,
    step: StrategyStepNode,
    record_type: str,
) -> str | None:
    sync_state.wdk_step_ids.pop(step.id, None)
    return await _execute_create(sync_state, site_id, step, record_type)


async def _validate_plan_params(
    plan: list[StepPushPlan],
    steps_by_id: dict[str, StrategyStepNode],
    site_id: str,
    record_type: str,
) -> None:
    callbacks: ValidationCallbacks = make_validation_callbacks(site_id)
    for entry in plan:
        step = steps_by_id.get(entry.step_id)
        if step is None or isinstance(entry.action, SkipAction):
            continue
        search_name = step.search_name or COMBINE_SEARCH_NAME
        if search_name == COMBINE_SEARCH_NAME:
            continue
        step.parameters = await validate_parameters(
            SearchContext(
                site_id=site_id, record_type=record_type, search_name=search_name
            ),
            parameters=dict(step.parameters),
            callbacks=callbacks,
        )


async def push_steps_with_plan(
    graph: StrategyGraph,
    sync_state: WDKSyncState,
    site_id: str,
    plan: list[StepPushPlan],
) -> PushOutcome:
    """Execute a push plan. Returns a PushOutcome with succeeded + failed step IDs.

    The loop continues after a failure so independent siblings still get
    pushed. A combine that depends on a failed input naturally short-circuits
    inside `_push_combine_step` because the input lacks a wdk_step_id, and
    that combine ends up in `failed`.
    """
    root_step = next(
        (graph.steps[sid] for sid in graph.roots if sid in graph.steps), None
    )
    if root_step is None:
        return PushOutcome(succeeded=[], failed=[])

    steps_by_id: dict[str, StrategyStepNode] = {
        s.id: s for s in walk_step_tree(root_step)
    }
    record_type = graph.record_type or "transcript"

    await _validate_plan_params(plan, steps_by_id, site_id, record_type)

    succeeded: list[str] = []
    failed: list[str] = []

    for entry in plan:
        step = steps_by_id.get(entry.step_id)
        if step is None:
            continue
        action = entry.action
        if isinstance(action, SkipAction):
            continue
        if isinstance(action, PatchAction):
            err = await _execute_patch(sync_state, site_id, step, record_type)
        elif isinstance(action, CreateAction):
            err = await _execute_create(sync_state, site_id, step, record_type)
        elif isinstance(action, RecreateAction):
            err = await _execute_recreate(sync_state, site_id, step, record_type)
        else:
            assert_never(action)
        if err is None:
            succeeded.append(step.id)
        else:
            failed.append(step.id)

    return PushOutcome(succeeded=succeeded, failed=failed)
