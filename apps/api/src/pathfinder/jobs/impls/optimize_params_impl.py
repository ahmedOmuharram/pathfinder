"""Worker-side impl for ``optimize_search_parameters``.

Moved from ``ai/tools/standalone/optimization.py``. The agent-side wrapper
is now a thin durable stub; all parameter-optimisation trials run here, on
the verification worker. Progress is emitted per trial via the injected
``TaskProgressEmitter`` so the UI sees each score update as it lands.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import pathfinder.services.parameter_optimization.core
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.tools.durable import TaskProgressEmitter
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


async def optimize_search_parameters_impl(
    *,
    context: Context,
    task_id: UUID,
    progress: TaskProgressEmitter,
    memory_store: MemoryStore | None,
    target: dict[str, Any] | OptimizationTarget,
    controls: dict[str, Any] | OptimizationControls,
    settings: dict[str, Any] | OptimizationSettings | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Run parameter optimisation against controls and return the result dict."""
    del task_id, memory_store

    # Opt into batched progress commits — budget is typically 30 trials and
    # each `progress.update` would otherwise be its own round-trip. The
    # runner's `progress.aclose()` flushes any residual.
    progress.batch_size = 8

    target_m = (
        target
        if isinstance(target, OptimizationTarget)
        else OptimizationTarget.model_validate(target)
    )
    controls_m = (
        controls
        if isinstance(controls, OptimizationControls)
        else OptimizationControls.model_validate(controls)
    )
    settings_m = (
        settings
        if isinstance(settings, OptimizationSettings)
        else OptimizationSettings.model_validate(settings or {})
    )

    specs, fixed_parameters, controls_extra_parameters = (
        _parse_and_validate_inputs(target_m, controls_m)
    )

    await progress.update(
        percent=0.0,
        message=f"Starting optimisation (budget={settings_m.budget})",
        data={
            "search_name": target_m.search_name,
            "budget": settings_m.budget,
            "objective": settings_m.objective,
        },
    )

    opt_inp = OptimizationInput(
        site_id=context.site_id,
        record_type=target_m.record_type,
        search_name=target_m.search_name,
        fixed_parameters=cast("dict[str, JSONValue]", fixed_parameters),
        parameter_space=specs,
        controls_search_name=controls_m.controls_search_name,
        controls_param_name=controls_m.controls_param_name,
        positive_controls=controls_m.positive_controls,
        negative_controls=controls_m.negative_controls,
        controls_value_format=cast(
            "ControlValueFormat", controls_m.controls_value_format
        ),
        controls_extra_parameters=cast(
            "dict[str, JSONValue]", controls_extra_parameters
        ),
        id_field=controls_m.id_field,
    )
    opt_cfg = OptimizationConfig(
        budget=settings_m.budget,
        objective=cast("OptimizationObjective", settings_m.objective),
        beta=settings_m.beta,
        method=cast("OptimizationMethod", settings_m.method),
        estimated_size_penalty=max(0.0, settings_m.estimated_size_penalty),
    )

    trial_count = 0

    async def _progress_callback(event: JSONObject) -> None:
        nonlocal trial_count
        event_kind = event.get("event")
        data = event.get("data") if isinstance(event.get("data"), dict) else None
        if event_kind == "trial_complete":
            trial_count += 1
            await progress.update(
                percent=min(0.95, trial_count / max(1, settings_m.budget)),
                message=f"Trial {trial_count}/{settings_m.budget} complete",
                data=cast("dict[str, Any]", data) if data is not None else None,
            )

    result = await pathfinder.services.parameter_optimization.core.optimize_search_parameters(
        opt_inp,
        config=opt_cfg,
        progress_callback=_progress_callback,
        check_cancelled=None,
    )

    result_json: dict[str, Any] = result.model_dump(by_alias=True, mode="json")
    await progress.update(
        percent=0.98,
        message="Exporting optimisation result",
        data=None,
    )
    await _attach_export(result_json, opt_inp.search_name)
    await progress.update(
        percent=1.0, message="Optimisation complete", data=None,
    )
    # Flush remaining buffered rows so callers querying task_progress
    # immediately see the full trial history. The runner's ``aclose()`` is
    # a safety net on top of this.
    await progress.flush()
    return result_json
