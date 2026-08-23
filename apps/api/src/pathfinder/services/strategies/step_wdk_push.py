"""WDK push logic for step creation.

A failed push leaves the step in the local graph for the sync service to
reconcile later.
"""

from typing import assert_never

from assistant_core.platform.logging import get_logger
from pydantic import BaseModel, ConfigDict

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.ast import (
    COMBINE_SEARCH_NAME,
)
from pathfinder.domain.strategy.graph_model import (
    StepKind,
    StepStatus,
    StrategyStep,
    step_status,
    wdk_search_name,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.integrations.veupathdb.strategy_api import StrategyAPI
from pathfinder.integrations.veupathdb.value_decoding import encode_params
from pathfinder.integrations.veupathdb.wdk_models import (
    CombinedStepSpec,
    NewStepSpec,
    PatchStepSpec,
    WDKSearchConfig,
)
from pathfinder.platform.errors import AppError, ValidationError
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
    """Step ids of a push plan, split by result and kept in plan order."""

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
    step: StrategyStep,
    site_id: str,
    record_type: str,
    search_name: str,
    parameters: dict[str, ParamValue],
) -> tuple[int | None, StepValidation | None, str | None]:
    """Push a newly created step to WDK and store its id on sync_state.

    A rejected push returns the reason in ``push_error`` and does not raise.
    """
    parsed_op: CombineOp | None = step.operator
    wdk_step_id: int | None = None
    wdk_validation: StepValidation | None = None
    push_error: str | None = None
    str_params: dict[str, str] = encode_params(parameters)
    try:
        api = get_strategy_api(site_id)
        is_binary = step.kind is StepKind.COMBINE
        is_transform = step.kind is StepKind.TRANSFORM

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
    step: StrategyStep,
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
    step: StrategyStep,
    record_type: str,
    parsed_op: CombineOp | None,
) -> int | None:
    """Push a combine step to WDK.

    Returns the WDK step ID or None if inputs are missing.
    """
    primary_wdk_id = (
        sync_state.wdk_step_ids.get(step.primary_input_id)
        if step.primary_input_id
        else None
    )
    secondary_wdk_id = (
        sync_state.wdk_step_ids.get(step.secondary_input_id)
        if step.secondary_input_id
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
        # GenesBySpanLogic takes span_a and span_b as AnswerParams. The step
        # tree wires both inputs, so only the primary id is passed here.
        # The search lives under "transcript" for every record type.
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
        CombinedStepSpec(
            primary_step_id=primary_wdk_id,
            secondary_step_id=secondary_wdk_id,
            boolean_operator=parsed_op,
            custom_name=step.display_name or None,
            wdk_weight=step.wdk_weight,
        ),
        record_type=record_type,
    )
    if step.expanded_strategy_id is not None:
        # The create-combined-step endpoint does not accept "expanded", so it
        # is set by a PATCH.
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
    step: StrategyStep,
    search_name: str,
    str_params: dict[str, str],
    record_type: str,
) -> int | None:
    """Push a transform step to WDK.

    Returns the WDK step ID or None if input is missing.
    """
    input_wdk_id = (
        sync_state.wdk_step_ids.get(step.primary_input_id)
        if step.primary_input_id
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
    step: StrategyStep,
    record_type: str,
) -> None:
    """Update an existing WDK step's search-config (parameters + weight)."""
    wdk_step_id = sync_state.wdk_step_ids[step.id]
    kind = step.kind.value

    # The params of a combine step are structural and never change.
    if kind == "combine":
        return
    str_params: dict[str, str] = encode_params(step.parameters)

    await api.update_step_search_config(
        step_id=wdk_step_id,
        search_config=WDKSearchConfig(parameters=str_params),
        record_type=record_type,
        search_name=wdk_search_name(step),
    )


async def _patch_combine_metadata(
    api: StrategyAPI,
    sync_state: WDKSyncState,
    step: StrategyStep,
) -> None:
    # A WDK combine operator is a creation-time param. Only the display name
    # and the weight accept a PATCH.
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
    step: StrategyStep,
    record_type: str,
) -> str | None:
    api = get_strategy_api(site_id)
    try:
        if step.kind.value == "combine":
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
    step: StrategyStep,
    record_type: str,
) -> str | None:
    wdk_step_id, _validation, push_error = await push_step_to_wdk(
        sync_state=sync_state,
        step=step,
        site_id=site_id,
        record_type=record_type,
        search_name=wdk_search_name(step),
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
    step: StrategyStep,
    record_type: str,
) -> str | None:
    sync_state.wdk_step_ids.pop(step.id, None)
    return await _execute_create(sync_state, site_id, step, record_type)


def defer_draft_steps(
    plan: list[StepPushPlan],
    *,
    steps_by_id: dict[str, StrategyStep],
    open_param_step_ids: set[str],
    existing_wdk_ids: dict[str, int],
) -> list[StepPushPlan]:
    """Replace the action of each step that is not ready with a skip.

    A step that is already in WDK is never deferred, because a draft is left
    out of the built strategy.
    """
    deferred: list[StepPushPlan] = []
    for entry in plan:
        step = steps_by_id.get(entry.step_id)
        already_live = entry.step_id in existing_wdk_ids
        status = (
            step_status(
                step,
                wdk_step_id=existing_wdk_ids.get(entry.step_id),
                validation=None,
                has_open_params=entry.step_id in open_param_step_ids,
            )
            if step is not None
            else StepStatus.BUILT
        )
        is_draft_to_defer = (
            step is not None
            and not status.is_pushable
            and not already_live
            and not isinstance(entry.action, SkipAction)
        )
        if is_draft_to_defer:
            deferred.append(
                StepPushPlan(
                    step_id=entry.step_id,
                    action=SkipAction(),
                    reason="draft: not ready to build yet",
                )
            )
            continue
        deferred.append(entry)
    return deferred


async def _validate_plan_params(
    plan: list[StepPushPlan],
    steps_by_id: dict[str, StrategyStep],
    site_id: str,
    record_type: str,
    existing_wdk_ids: dict[str, int],
) -> set[str]:
    """Canonicalize the params of each pushable step in place.

    An incomplete step that is already in WDK raises instead of being
    reported, because a draft is left out of the built strategy.
    """
    callbacks: ValidationCallbacks = make_validation_callbacks(site_id)
    incomplete: set[str] = set()
    for entry in plan:
        step = steps_by_id.get(entry.step_id)
        if step is None or isinstance(entry.action, SkipAction):
            continue
        search_name = step.search_name or COMBINE_SEARCH_NAME
        if search_name == COMBINE_SEARCH_NAME:
            continue
        try:
            step.parameters = (
                await validate_parameters(
                    SearchContext(
                        site_id=site_id,
                        record_type=record_type,
                        search_name=search_name,
                    ),
                    parameters=dict(step.parameters),
                    callbacks=callbacks,
                )
            ).params
        except ValidationError:
            if entry.step_id in existing_wdk_ids:
                raise
            incomplete.add(entry.step_id)
    return incomplete


async def push_steps_with_plan(
    graph: StrategyGraph,
    sync_state: WDKSyncState,
    site_id: str,
    plan: list[StepPushPlan],
) -> PushOutcome:
    """Execute a push plan.

    A failed step does not stop the plan. A combine whose input failed has no
    input id, so it also fails.
    """
    root_step = next(
        (graph.steps[sid] for sid in graph.roots if sid in graph.steps), None
    )
    if root_step is None:
        return PushOutcome(succeeded=[], failed=[])

    steps_by_id: dict[str, StrategyStep] = dict(graph.steps)
    record_type = graph.record_type or "transcript"

    incomplete = await _validate_plan_params(
        plan, steps_by_id, site_id, record_type, sync_state.wdk_step_ids
    )
    plan = defer_draft_steps(
        plan,
        steps_by_id=steps_by_id,
        open_param_step_ids=incomplete,
        existing_wdk_ids=sync_state.wdk_step_ids,
    )

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
