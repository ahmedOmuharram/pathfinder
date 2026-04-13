"""Standalone optimization tools for pydantic-ai agents.

Provides:
- ``optimize_search_parameters`` -- optimise search parameters against control gene lists

Progressive emission approach (plan Step 4c.10): **Approach C** — accumulate
all progress snapshots into `ToolReturn.metadata` and emit them in one batch
when the tool returns. Rationale:

- pydantic-ai 1.80's ``VercelAIAdapter`` exposes no in-tool ``emit()`` on
  the event stream (Approach A unavailable — see `VercelAIEventStream`
  public surface has no `emit`, `publish`, or direct chunk injection).
- Splitting into ``start_optimize`` + ``optimize_trial`` sub-tools (Approach B)
  would trigger one round-trip through the LLM per trial, which is both
  expensive and breaks cancellation semantics — the optimizer holds state
  (Bayesian suggester, best score, Pareto set) that would need to be
  serialized/deserialized per trial.
- Accepting Approach C: progress arrives as a single burst of data-parts
  when the tool completes. The UI progress panel still renders all
  snapshots in order. Known limitation: mid-run progress is not visible
  until the optimizer finishes; the user sees "pending" until then.
"""

from __future__ import annotations

import json
from typing import cast

from pydantic import ValidationError
from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn
from pydantic_ai.ui.vercel_ai.response_types import DataChunk

import pathfinder.services.parameter_optimization.core
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone._optimization_models import (
    OptimizationControls,
    OptimizationSettings,
    OptimizationTarget,
    _attach_export,
    _parse_and_validate_inputs,
)
from pathfinder.platform.types import JSONObject, JSONValue
from pathfinder.services.experiment.types import (
    ControlValueFormat,
    OptimizationObjective,
)
from pathfinder.services.parameter_optimization import (
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
) -> ToolReturn[str] | str:
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

    # Approach C: accumulate progress events into a list; flush into
    # ToolReturn.metadata at the end of the tool call.
    progress_events: list[JSONObject] = []

    async def progress_callback(event: JSONObject) -> None:
        progress_events.append(event)

    result = await pathfinder.services.parameter_optimization.core.optimize_search_parameters(
        opt_inp,
        config=opt_cfg,
        progress_callback=progress_callback,
        check_cancelled=cancel_event.is_set,
    )

    result_json = result.model_dump(by_alias=True, mode="json")
    await _attach_export(result_json, opt_inp.search_name)

    # Emit one data-optimization-snapshot DataChunk per progress event.
    metadata: list[DataChunk] = []
    for ev in progress_events:
        data = ev.get("data") if isinstance(ev, dict) else None
        if isinstance(data, dict):
            metadata.append(
                DataChunk(type="data-optimization-snapshot", data=data),
            )
    return ToolReturn(
        return_value=json.dumps(result_json),
        metadata=metadata,
    )
