"""Planner-mode tool for search parameter optimization.

Provides :class:`OptimizationToolsMixin` with the long-running
``optimize_search_parameters`` tool.
"""

import json
from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    OptimizationObjective,
)
from veupath_chatbot.services.parameter_optimization import (
    OptimizationConfig,
    OptimizationMethod,
    ParameterSpec,
)
from veupath_chatbot.services.parameter_optimization import (
    optimize_search_parameters as _run_optimization,
)
from veupath_chatbot.services.parameter_optimization import (
    result_to_json as _opt_result_to_json,
)


class OptimizationToolsMixin:
    """Kani tool mixin for search parameter optimization."""

    site_id: str = ""

    async def _emit_event(self, event: JSONObject) -> None:
        """Emit an SSE event. Override in subclass to push to streaming queue."""
        pass

    @ai_function()
    async def optimize_search_parameters(
        self,
        record_type: Annotated[
            str, AIParam(desc="WDK record type (e.g. 'transcript')")
        ],
        search_name: Annotated[
            str, AIParam(desc="WDK search/question urlSegment to optimise")
        ],
        parameter_space_json: Annotated[
            str,
            AIParam(
                desc=(
                    "JSON array of parameters to optimise. Each entry is an object: "
                    '{"name": "<paramName>", "type": "numeric"|"integer"|"categorical", '
                    '"min": <number>, "max": <number>, "logScale"?: bool, "step"?: <number>, "choices"?: ["a","b"]}. '
                    "Example: "
                    '[{"name":"fold_change","type":"numeric","min":1.5,"max":20}]'
                )
            ),
        ],
        fixed_parameters_json: Annotated[
            str,
            AIParam(
                desc=(
                    "JSON object of parameters held constant during optimisation. "
                    'Example: {"organism":"P. falciparum 3D7","direction":"up-regulated"}'
                )
            ),
        ],
        controls_search_name: Annotated[
            str,
            AIParam(desc="Search that accepts a list of record IDs (for controls)"),
        ],
        controls_param_name: Annotated[
            str,
            AIParam(desc="Parameter name within controls_search_name that accepts IDs"),
        ],
        positive_controls: Annotated[
            list[str] | None,
            AIParam(desc="Known-positive IDs that should be returned"),
        ] = None,
        negative_controls: Annotated[
            list[str] | None,
            AIParam(desc="Known-negative IDs that should NOT be returned"),
        ] = None,
        budget: Annotated[
            int, AIParam(desc="Max number of trials (default 15, max 50)")
        ] = 15,
        objective: Annotated[
            str,
            AIParam(
                desc=(
                    "Scoring objective: 'f1' (balanced, default), 'recall', "
                    "'precision', 'f_beta' (specify beta), or 'custom'"
                )
            ),
        ] = "f1",
        beta: Annotated[
            float, AIParam(desc="Beta value for f_beta objective (default 1.0)")
        ] = 1.0,
        method: Annotated[
            str,
            AIParam(
                desc="Optimisation method: 'bayesian' (default, recommended), 'grid', or 'random'"
            ),
        ] = "bayesian",
        controls_value_format: Annotated[
            ControlValueFormat,
            AIParam(desc="How to encode the control ID list"),
        ] = "newline",
        controls_extra_parameters_json: Annotated[
            str | None,
            AIParam(
                desc="JSON object of extra fixed parameters for the controls search"
            ),
        ] = None,
        id_field: Annotated[
            str | None,
            AIParam(desc="Optional record-id field name for answer records"),
        ] = None,
        result_count_penalty: Annotated[
            float,
            AIParam(
                desc=(
                    "Weight for penalising large result sets (0 = off, 0.1 = tiebreaker, "
                    "higher = strongly prefer tighter results). Default 0.1."
                )
            ),
        ] = 0.1,
    ) -> str:
        """Optimise search parameters against positive/negative control gene lists.

        Runs multiple trials, varying the parameters in `parameter_space` while
        holding `fixed_parameters` constant. Each trial evaluates the search
        against the controls and scores the result. Returns the best
        configuration, all trials, Pareto frontier, and sensitivity analysis.

        This is a long-running operation. The user will see real-time progress
        in the UI. Always confirm the plan with the user before calling this.
        """

        def _err(msg: str) -> str:
            return json.dumps({"error": msg})

        # -- scalar argument validation ----------------------------------------

        if not record_type or not record_type.strip():
            return _err("record_type is required and must be a non-empty string.")

        if not search_name or not search_name.strip():
            return _err("search_name is required and must be a non-empty string.")

        if not controls_search_name or not controls_search_name.strip():
            return _err(
                "controls_search_name is required and must be a non-empty string."
            )

        if not controls_param_name or not controls_param_name.strip():
            return _err(
                "controls_param_name is required and must be a non-empty string."
            )

        has_positives = positive_controls and len(positive_controls) > 0
        has_negatives = negative_controls and len(negative_controls) > 0
        if not has_positives and not has_negatives:
            return _err(
                "At least one of positive_controls or negative_controls must be "
                "provided with at least one ID. Without any controls the optimiser "
                "has no signal to score against."
            )

        _valid_objectives = ("f1", "f_beta", "recall", "precision", "custom")
        if objective not in _valid_objectives:
            return _err(
                f"Invalid objective '{objective}'. "
                f"Must be one of: {', '.join(repr(o) for o in _valid_objectives)}."
            )

        _valid_methods = ("bayesian", "grid", "random")
        if method not in _valid_methods:
            return _err(
                f"Invalid method '{method}'. "
                f"Must be one of: {', '.join(repr(m) for m in _valid_methods)}."
            )

        _valid_formats: tuple[str, ...] = ("newline", "json_list", "comma")
        if controls_value_format not in _valid_formats:
            return _err(
                f"Invalid controls_value_format '{controls_value_format}'. "
                f"Must be one of: {', '.join(repr(f) for f in _valid_formats)}."
            )

        if not isinstance(budget, int) or budget < 1:
            return _err(f"budget must be a positive integer, got {budget!r}.")
        if budget > 50:
            return _err(
                f"budget={budget} exceeds the maximum of 50. "
                "Use a smaller budget or narrow the parameter space."
            )

        if objective == "f_beta" and (not isinstance(beta, (int, float)) or beta <= 0):
            return _err(
                f"beta must be a positive number when objective is 'f_beta', got {beta!r}."
            )

        # -- JSON argument parsing & validation --------------------------------

        try:
            raw_space = json.loads(parameter_space_json)
        except (json.JSONDecodeError, TypeError) as exc:
            return _err(f"parameter_space_json is not valid JSON: {exc}")

        if not isinstance(raw_space, list):
            return _err("parameter_space_json must be a JSON array.")

        if len(raw_space) == 0:
            return _err(
                "parameter_space_json is an empty array. "
                "Provide at least one parameter to optimise."
            )

        try:
            fixed_parameters: JSONObject = (
                json.loads(fixed_parameters_json) if fixed_parameters_json else {}
            )
        except (json.JSONDecodeError, TypeError) as exc:
            return _err(f"fixed_parameters_json is not valid JSON: {exc}")

        if not isinstance(fixed_parameters, dict):
            return _err(
                "fixed_parameters_json must be a JSON object (dict), "
                f"got {type(fixed_parameters).__name__}."
            )

        controls_extra_parameters: JSONObject | None = None
        if controls_extra_parameters_json:
            try:
                controls_extra_parameters = json.loads(controls_extra_parameters_json)
            except (json.JSONDecodeError, TypeError) as exc:
                return _err(f"controls_extra_parameters_json is not valid JSON: {exc}")
            if not isinstance(controls_extra_parameters, dict):
                return _err(
                    "controls_extra_parameters_json must be a JSON object (dict), "
                    f"got {type(controls_extra_parameters).__name__}."
                )

        # -- parameter_space entry validation ----------------------------------

        _valid_param_types = ("numeric", "integer", "categorical")

        specs: list[ParameterSpec] = []
        seen_names: set[str] = set()
        for i, p in enumerate(raw_space):
            if not isinstance(p, dict):
                return _err(
                    f"parameter_space[{i}] must be an object, got {type(p).__name__}."
                )

            pname = p.get("name")
            if not pname or not isinstance(pname, str):
                return _err(f"parameter_space[{i}] is missing a 'name' string field.")

            if pname in seen_names:
                return _err(
                    f"parameter_space[{i}]: duplicate parameter name '{pname}'. "
                    "Each parameter must have a unique name."
                )
            seen_names.add(pname)

            ptype = p.get("type")
            if ptype not in _valid_param_types:
                return _err(
                    f"parameter_space[{i}] ('{pname}'): "
                    f"invalid type '{ptype}'. "
                    f"Must be one of: {', '.join(repr(t) for t in _valid_param_types)}."
                )

            if ptype in ("numeric", "integer"):
                if "min" not in p or "max" not in p:
                    return _err(
                        f"parameter_space[{i}] ('{pname}'): "
                        f"type '{ptype}' requires both 'min' and 'max' fields."
                    )
                try:
                    lo = float(p["min"])
                    hi = float(p["max"])
                except TypeError, ValueError:
                    return _err(
                        f"parameter_space[{i}] ('{pname}'): "
                        f"'min' and 'max' must be numbers, "
                        f"got min={p['min']!r}, max={p['max']!r}."
                    )
                if lo >= hi:
                    return _err(
                        f"parameter_space[{i}] ('{pname}'): "
                        f"'min' ({lo}) must be strictly less than 'max' ({hi})."
                    )
                if "step" in p:
                    try:
                        step_val = float(p["step"])
                    except TypeError, ValueError:
                        return _err(
                            f"parameter_space[{i}] ('{pname}'): "
                            f"'step' must be a number, got {p['step']!r}."
                        )
                    if step_val <= 0:
                        return _err(
                            f"parameter_space[{i}] ('{pname}'): "
                            f"'step' must be positive, got {step_val}."
                        )

            if ptype == "categorical":
                choices_raw = p.get("choices")
                if not isinstance(choices_raw, list) or len(choices_raw) == 0:
                    return _err(
                        f"parameter_space[{i}] ('{pname}'): "
                        f"type 'categorical' requires a non-empty 'choices' array."
                    )

            specs.append(
                ParameterSpec(
                    name=pname,
                    param_type=ptype,
                    min_value=float(p["min"]) if "min" in p else None,
                    max_value=float(p["max"]) if "max" in p else None,
                    log_scale=bool(p.get("logScale", False)),
                    step=float(p["step"]) if "step" in p else None,
                    choices=(
                        [str(c) for c in p["choices"]]
                        if "choices" in p and isinstance(p["choices"], list)
                        else None
                    ),
                )
            )

        config = OptimizationConfig(
            budget=budget,
            objective=cast(OptimizationObjective, objective),
            beta=beta,
            method=cast(OptimizationMethod, method),
            result_count_penalty=max(0.0, result_count_penalty),
        )

        cancel_event = getattr(self, "_cancel_event", None)

        result = await _run_optimization(
            site_id=self.site_id,
            record_type=record_type,
            search_name=search_name,
            fixed_parameters=fixed_parameters,
            parameter_space=specs,
            controls_search_name=controls_search_name,
            controls_param_name=controls_param_name,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
            controls_value_format=controls_value_format,
            controls_extra_parameters=controls_extra_parameters,
            id_field=id_field,
            config=config,
            progress_callback=self._emit_event,
            check_cancelled=(cancel_event.is_set if cancel_event is not None else None),
        )

        result_json = _opt_result_to_json(result)

        # Auto-generate exports.
        try:
            from veupath_chatbot.services.export import get_export_service

            svc = get_export_service()
            name = f"{search_name}_optimization"
            json_export = await svc.export_json(result_json, name)
            result_json["downloads"] = {
                "json": json_export.url,
                "expiresInSeconds": json_export.expires_in_seconds,
            }
        except Exception:
            pass

        return json.dumps(result_json)
