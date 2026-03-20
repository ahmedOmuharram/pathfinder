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
from veupath_chatbot.services.export import get_export_service
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

_VALID_OBJECTIVES = ("f1", "f_beta", "recall", "precision", "custom")
_VALID_METHODS = ("bayesian", "grid", "random")
_VALID_FORMATS: tuple[str, ...] = ("newline", "json_list", "comma")
_VALID_PARAM_TYPES = ("numeric", "integer", "categorical")
_MAX_BUDGET = 50


def _err(msg: str) -> str:
    return json.dumps({"error": msg})


def _require_non_empty(value: str, name: str) -> str | None:
    """Return error if value is empty/whitespace, otherwise None."""
    if not value or not value.strip():
        return _err(f"{name} is required and must be a non-empty string.")
    return None


def _validate_required_fields(
    *,
    record_type: str,
    search_name: str,
    controls_search_name: str,
    controls_param_name: str,
    positive_controls: list[str] | None,
    negative_controls: list[str] | None,
) -> str | None:
    """Validate that required fields are present."""
    for value, name in [
        (record_type, "record_type"),
        (search_name, "search_name"),
        (controls_search_name, "controls_search_name"),
        (controls_param_name, "controls_param_name"),
    ]:
        error = _require_non_empty(value, name)
        if error is not None:
            return error

    has_positives = positive_controls and len(positive_controls) > 0
    has_negatives = negative_controls and len(negative_controls) > 0
    if not has_positives and not has_negatives:
        return _err(
            "At least one of positive_controls or negative_controls must be "
            "provided with at least one ID. Without any controls the optimiser "
            "has no signal to score against."
        )
    return None


def _validate_enum_and_budget(
    *,
    objective: str,
    method: str,
    controls_value_format: str,
    budget: int,
    beta: float,
) -> str | None:
    """Validate enum choices and budget constraints."""
    if objective not in _VALID_OBJECTIVES:
        return _err(
            f"Invalid objective '{objective}'. "
            f"Must be one of: {', '.join(repr(o) for o in _VALID_OBJECTIVES)}."
        )
    if method not in _VALID_METHODS:
        return _err(
            f"Invalid method '{method}'. "
            f"Must be one of: {', '.join(repr(m) for m in _VALID_METHODS)}."
        )
    if controls_value_format not in _VALID_FORMATS:
        return _err(
            f"Invalid controls_value_format '{controls_value_format}'. "
            f"Must be one of: {', '.join(repr(f) for f in _VALID_FORMATS)}."
        )
    if not isinstance(budget, int) or budget < 1:
        return _err(f"budget must be a positive integer, got {budget!r}.")
    if budget > _MAX_BUDGET:
        return _err(
            f"budget={budget} exceeds the maximum of {_MAX_BUDGET}. "
            "Use a smaller budget or narrow the parameter space."
        )
    if objective == "f_beta" and (not isinstance(beta, (int, float)) or beta <= 0):
        return _err(
            f"beta must be a positive number when objective is 'f_beta', got {beta!r}."
        )
    return None


def _parse_json_list(raw_json: str, field_name: str) -> list[object] | str:
    """Parse a JSON array field. Returns parsed list or error string."""
    try:
        parsed = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return _err(f"{field_name} is not valid JSON: {exc}")
    if not isinstance(parsed, list):
        return _err(f"{field_name} must be a JSON array.")
    if len(parsed) == 0:
        return _err(
            f"{field_name} is an empty array. Provide at least one parameter to optimise."
        )
    return parsed


def _parse_json_object(
    raw_json: str | None, field_name: str, default: JSONObject | None = None
) -> JSONObject | None | str:
    """Parse a JSON object field. Returns parsed dict, None, or error string."""
    if not raw_json:
        return default if default is not None else {}
    try:
        parsed = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return _err(f"{field_name} is not valid JSON: {exc}")
    if not isinstance(parsed, dict):
        return _err(
            f"{field_name} must be a JSON object (dict), got {type(parsed).__name__}."
        )
    return parsed


def _parse_json_args(
    parameter_space_json: str,
    fixed_parameters_json: str,
    controls_extra_parameters_json: str | None,
) -> tuple[list[object], JSONObject, JSONObject | None] | str:
    """Parse JSON string arguments. Returns parsed data or error string."""
    raw_space = _parse_json_list(parameter_space_json, "parameter_space_json")
    if isinstance(raw_space, str):
        return raw_space

    fixed_result = _parse_json_object(
        fixed_parameters_json, "fixed_parameters_json", default={}
    )
    if isinstance(fixed_result, str):
        return fixed_result
    fixed_parameters: JSONObject = fixed_result or {}

    controls_result = _parse_json_object(
        controls_extra_parameters_json, "controls_extra_parameters_json"
    )
    if isinstance(controls_result, str):
        return controls_result

    return raw_space, fixed_parameters, controls_result


def _validate_min_max(i: int, pname: str, p: dict[str, object]) -> str | None:
    """Validate that min/max are present and valid numbers with min < max."""
    if "min" not in p or "max" not in p:
        return _err(
            f"parameter_space[{i}] ('{pname}'): "
            f"type '{p.get('type')}' requires both 'min' and 'max' fields."
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
    return None


def _validate_step_field(i: int, pname: str, p: dict[str, object]) -> str | None:
    """Validate optional step field."""
    if "step" not in p:
        return None
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
    return None


def _validate_numeric_param(i: int, pname: str, p: dict[str, object]) -> str | None:
    """Validate numeric/integer parameter bounds. Returns error or None."""
    error = _validate_min_max(i, pname, p)
    if error is not None:
        return error
    return _validate_step_field(i, pname, p)


def _validate_single_param_entry(
    i: int,
    p: object,
    seen_names: set[str],
) -> tuple[str, str, dict[str, object]] | str:
    """Validate a single parameter entry. Returns (pname, ptype, p_dict) or error."""
    if not isinstance(p, dict):
        return _err(f"parameter_space[{i}] must be an object, got {type(p).__name__}.")
    pname = p.get("name")
    if not pname or not isinstance(pname, str):
        return _err(f"parameter_space[{i}] is missing a 'name' string field.")
    if pname in seen_names:
        return _err(
            f"parameter_space[{i}]: duplicate parameter name '{pname}'. "
            "Each parameter must have a unique name."
        )
    ptype = p.get("type")
    if ptype not in _VALID_PARAM_TYPES:
        return _err(
            f"parameter_space[{i}] ('{pname}'): "
            f"invalid type '{ptype}'. "
            f"Must be one of: {', '.join(repr(t) for t in _VALID_PARAM_TYPES)}."
        )
    return pname, str(ptype), p


def _validate_parameter_space(
    raw_space: list[object],
) -> list[ParameterSpec] | str:
    """Validate and parse parameter space entries. Returns specs or error."""
    specs: list[ParameterSpec] = []
    seen_names: set[str] = set()
    for i, p in enumerate(raw_space):
        entry_result = _validate_single_param_entry(i, p, seen_names)
        if isinstance(entry_result, str):
            return entry_result
        pname, ptype, p_dict = entry_result
        seen_names.add(pname)

        if ptype in ("numeric", "integer"):
            numeric_error = _validate_numeric_param(i, pname, p_dict)
            if numeric_error is not None:
                return numeric_error

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

    return specs


class OptimizationToolsMixin:
    """Kani tool mixin for search parameter optimization."""

    site_id: str = ""

    async def _emit_event(self, event: JSONObject) -> None:
        """Emit an SSE event. Override in subclass to push to streaming queue."""

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
        *,
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
        # Required fields
        req_error = _validate_required_fields(
            record_type=record_type,
            search_name=search_name,
            controls_search_name=controls_search_name,
            controls_param_name=controls_param_name,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
        )
        if req_error is not None:
            return req_error

        # Enum and budget validation
        enum_error = _validate_enum_and_budget(
            objective=objective,
            method=method,
            controls_value_format=controls_value_format,
            budget=budget,
            beta=beta,
        )
        if enum_error is not None:
            return enum_error

        # JSON parsing
        json_result = _parse_json_args(
            parameter_space_json, fixed_parameters_json, controls_extra_parameters_json
        )
        if isinstance(json_result, str):
            return json_result
        raw_space, fixed_parameters, controls_extra_parameters = json_result

        # Parameter space validation
        specs_result = _validate_parameter_space(raw_space)
        if isinstance(specs_result, str):
            return specs_result

        return await self._run_optimization(
            record_type=record_type,
            search_name=search_name,
            fixed_parameters=fixed_parameters,
            specs=specs_result,
            controls_search_name=controls_search_name,
            controls_param_name=controls_param_name,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
            budget=budget,
            objective=objective,
            beta=beta,
            method=method,
            controls_value_format=controls_value_format,
            controls_extra_parameters=controls_extra_parameters,
            id_field=id_field,
            result_count_penalty=result_count_penalty,
        )

    async def _run_optimization(
        self,
        *,
        record_type: str,
        search_name: str,
        fixed_parameters: JSONObject,
        specs: list[ParameterSpec],
        controls_search_name: str,
        controls_param_name: str,
        positive_controls: list[str] | None,
        negative_controls: list[str] | None,
        budget: int,
        objective: str,
        beta: float,
        method: str,
        controls_value_format: ControlValueFormat,
        controls_extra_parameters: JSONObject | None,
        id_field: str | None,
        result_count_penalty: float,
    ) -> str:
        """Execute the optimization and return JSON result."""
        config = OptimizationConfig(
            budget=budget,
            objective=cast("OptimizationObjective", objective),
            beta=beta,
            method=cast("OptimizationMethod", method),
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
        await _attach_export(result_json, search_name)
        return json.dumps(result_json)


async def _attach_export(result_json: JSONObject, search_name: str) -> None:
    """Try to attach an export download URL to the result."""
    try:
        svc = get_export_service()
        name = f"{search_name}_optimization"
        json_export = await svc.export_json(result_json, name)
        result_json["downloads"] = {
            "json": json_export.url,
            "expiresInSeconds": json_export.expires_in_seconds,
        }
    except OSError, ValueError, TypeError, KeyError:
        pass
