"""Experiment strategy refinement service.

Provides the shared business logic for adding steps to an experiment's
WDK strategy — used by both the HTTP endpoint and the AI refinement tools.
"""

from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.integrations.veupathdb.strategy_api import StrategyAPI
from pathfinder.integrations.veupathdb.wdk_models import (
    CombinedStepSpec,
    NewStepSpec,
    WDKSearchConfig,
    WDKStepTree,
)
from pathfinder.platform.errors import AppError, NotFoundError
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.experiment.store import ExperimentStore
from pathfinder.services.experiment.types import Experiment


class RefineResult(CamelModel):
    """Result of a strategy refinement operation."""

    new_step_id: int
    operator: CombineOp | None = None
    estimated_size: int | None = None


def _require_strategy(exp: Experiment) -> tuple[int, int]:
    """Return (strategy_id, step_id) or raise NotFoundError."""
    if not exp.wdk_strategy_id or not exp.wdk_step_id:
        raise NotFoundError(title="No WDK strategy for this experiment")
    return exp.wdk_strategy_id, exp.wdk_step_id


async def combine_steps(
    api: StrategyAPI,
    exp: Experiment,
    secondary_step_id: int,
    operator: CombineOp,
    store: ExperimentStore,
    custom_name: str | None = None,
) -> RefineResult:
    """Create a boolean-combine step and update the experiment strategy.

    This is the core combine operation: given an existing experiment step
    and a secondary step ID, it creates the combined step, rebuilds the
    step tree, and persists the updated experiment.
    """
    strategy_id, current_step_id = _require_strategy(exp)

    name = custom_name or f"{operator} refinement"
    combined = await api.create_combined_step(
        CombinedStepSpec(
            primary_step_id=current_step_id,
            secondary_step_id=secondary_step_id,
            boolean_operator=operator,
            custom_name=name,
        ),
        record_type=exp.config.record_type,
    )
    combined_id = combined.id

    new_tree = WDKStepTree(
        step_id=combined_id,
        primary_input=WDKStepTree(step_id=current_step_id),
        secondary_input=WDKStepTree(step_id=secondary_step_id),
    )
    await api.update_strategy(strategy_id, step_tree=new_tree)

    exp.wdk_step_id = combined_id
    store.save(exp)

    try:
        count = await api.get_step_count(combined_id)
    except AppError:
        count = None

    return RefineResult(
        new_step_id=combined_id,
        operator=operator,
        estimated_size=count,
    )


async def combine_with_search(
    api: StrategyAPI,
    exp: Experiment,
    search_name: str,
    parameters: dict[str, str],
    operator: CombineOp,
    store: ExperimentStore,
) -> RefineResult:
    """Create a search step and combine it with the experiment's current step."""
    _require_strategy(exp)

    new_step = await api.create_step(
        NewStepSpec(
            search_name=search_name,
            search_config=WDKSearchConfig(parameters=parameters),
            custom_name=f"Refinement: {search_name}",
        ),
        record_type=exp.config.record_type,
    )

    return await combine_steps(
        api=api,
        exp=exp,
        secondary_step_id=new_step.id,
        operator=operator,
        store=store,
    )


async def apply_transform(
    api: StrategyAPI,
    exp: Experiment,
    transform_name: str,
    parameters: dict[str, str],
    store: ExperimentStore,
) -> RefineResult:
    """Apply a transform step to the experiment's current step."""
    strategy_id, current_step_id = _require_strategy(exp)

    new_step = await api.create_transform_step(
        NewStepSpec(
            search_name=transform_name,
            search_config=WDKSearchConfig(parameters=parameters),
            custom_name=f"Transform: {transform_name}",
        ),
        input_step_id=current_step_id,
        record_type=exp.config.record_type,
    )
    new_step_id = new_step.id

    new_tree = WDKStepTree(
        step_id=new_step_id,
        primary_input=WDKStepTree(step_id=current_step_id),
    )
    await api.update_strategy(strategy_id, step_tree=new_tree)

    exp.wdk_step_id = new_step_id
    store.save(exp)

    try:
        count = await api.get_step_count(new_step_id)
    except AppError:
        count = None

    return RefineResult(
        new_step_id=new_step_id,
        estimated_size=count,
    )
