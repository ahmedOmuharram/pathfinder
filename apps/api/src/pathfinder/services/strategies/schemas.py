"""Service-layer strategy DTOs shared across services, AI, and transport."""

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.strategy.ast import (
    StepAnalysis,
    StepFilter,
    StepReport,
    StrategyStepNode,
)
from pathfinder.domain.strategy.ops import ColocationParams
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.platform.pydantic_base import CamelModel


class StepResponse(CamelModel):
    """Strategy step — WDK-aligned fields."""

    id: str
    kind: str | None = None
    display_name: str | None = None
    search_name: str | None = None
    record_type: str | None = None
    parameters: dict[str, ParamValue] | None = None
    operator: str | None = None
    colocation_params: ColocationParams | None = None
    primary_input_step_id: str | None = None
    secondary_input_step_id: str | None = None
    estimated_size: int | None = None
    wdk_step_id: int | None = None
    is_built: bool = False
    is_filtered: bool = False
    wdk_push_error: str | None = None
    validation: StepValidation | None = None
    filters: list[StepFilter] | None = None
    analyses: list[StepAnalysis] | None = None
    reports: list[StepReport] | None = None
    expanded_strategy_id: int | None = None
    expanded_name: str | None = None


def step_response_from_strategy_ast(
    payload: StrategyAst, step: StrategyStepNode
) -> StepResponse:
    counts = payload.step_counts or {}
    ids = payload.wdk_step_ids or {}
    validations = payload.step_validations or {}

    wdk_step_id = ids.get(step.id)
    if wdk_step_id is None and step.id.isdigit():
        wdk_step_id = int(step.id)

    return StepResponse(
        id=step.id,
        kind=step.infer_kind(),
        display_name=step.display_label,
        search_name=step.search_name,
        record_type=payload.record_type,
        parameters=step.parameters,
        operator=step.operator.value if step.operator else None,
        colocation_params=step.colocation_params,
        primary_input_step_id=step.primary_input.id if step.primary_input else None,
        secondary_input_step_id=step.secondary_input.id
        if step.secondary_input
        else None,
        estimated_size=counts.get(step.id),
        wdk_step_id=wdk_step_id,
        is_built=wdk_step_id is not None,
        is_filtered=bool(step.filters),
        validation=validations.get(step.id),
        filters=step.filters or None,
        analyses=step.analyses or None,
        reports=step.reports or None,
        expanded_strategy_id=step.expanded_strategy_id,
        expanded_name=step.expanded_name,
    )
