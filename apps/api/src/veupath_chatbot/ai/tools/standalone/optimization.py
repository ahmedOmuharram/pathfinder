"""Standalone optimization tools for pydantic-ai agents.

Provides:
- ``optimize_search_parameters`` -- optimise search parameters against control gene lists
"""

import json
from typing import cast

from pydantic import ValidationError
from pydantic_ai import RunContext

import veupath_chatbot.services.parameter_optimization.core
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.tools.standalone._optimization_models import (
    OptimizationControls,
    OptimizationSettings,
    OptimizationTarget,
    _attach_export,
    _parse_and_validate_inputs,
)
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    OptimizationObjective,
)
from veupath_chatbot.services.parameter_optimization import (
    OptimizationConfig,
    OptimizationInput,
    OptimizationMethod,
)

_DEFAULT_SETTINGS = OptimizationSettings()


def _err(msg: str) -> str:
    return json.dumps({"error": msg})


async def optimize_search_parameters(
    ctx: RunContext[AgentDeps],
    target: OptimizationTarget,
    controls: OptimizationControls,
    settings: OptimizationSettings = _DEFAULT_SETTINGS,
) -> str:
    """Optimise search parameters against positive/negative control gene lists.

    Runs multiple trials, varying the parameters in ``parameter_space`` while
    holding ``fixed_parameters`` constant. Each trial evaluates the search
    against the controls and scores the result. Returns the best
    configuration, all trials, Pareto frontier, and sensitivity analysis.

    This is a long-running operation. The user will see real-time progress
    in the UI. Always confirm the plan with the user before calling this.

    Args:
        target: Target search to optimise.
        controls: Control sets for scoring.
        settings: Optimisation hyperparameters.
    """
    deps = ctx.deps
    try:
        specs, fixed_parameters, controls_extra_parameters = (
            _parse_and_validate_inputs(target, controls)
        )
    except (ValueError, ValidationError) as exc:
        return _err(str(exc))

    opt_inp = OptimizationInput(
        site_id=deps.site_id,
        record_type=target.record_type,
        search_name=target.search_name,
        fixed_parameters=cast("dict[str, JSONValue]", fixed_parameters),
        parameter_space=specs,
        controls_search_name=controls.controls_search_name,
        controls_param_name=controls.controls_param_name,
        positive_controls=controls.positive_controls,
        negative_controls=controls.negative_controls,
        controls_value_format=cast("ControlValueFormat", controls.controls_value_format),
        controls_extra_parameters=cast("dict[str, JSONValue]", controls_extra_parameters),
        id_field=controls.id_field,
    )
    opt_cfg = OptimizationConfig(
        budget=settings.budget,
        objective=cast("OptimizationObjective", settings.objective),
        beta=settings.beta,
        method=cast("OptimizationMethod", settings.method),
        estimated_size_penalty=max(0.0, settings.estimated_size_penalty),
    )

    cancel_event = deps.cancel_event

    async def progress_callback(event: JSONObject) -> None:
        deps.emit_event(event)

    result = await veupath_chatbot.services.parameter_optimization.core.optimize_search_parameters(
        opt_inp,
        config=opt_cfg,
        progress_callback=progress_callback,
        check_cancelled=cancel_event.is_set,
    )

    result_json = result.model_dump(by_alias=True, mode="json")
    await _attach_export(result_json, opt_inp.search_name)
    return json.dumps(result_json)
