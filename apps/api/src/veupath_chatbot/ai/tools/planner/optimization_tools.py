"""Planner-mode tool for search parameter optimization.

Provides :class:`OptimizationToolsMixin` with the long-running
``optimize_search_parameters`` tool.
"""

import json
from typing import Annotated

from kani import AIParam, ai_function
from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    OptimizationObjective,
)
from veupath_chatbot.services.export import get_export_service
from veupath_chatbot.services.parameter_optimization import (
    OptimizationConfig,
    OptimizationInput,
    OptimizationMethod,
    ParameterSpec,
    optimize_search_parameters,
    result_to_json,
)

_MAX_BUDGET = 50
_NONEMPTY = StringConstraints(min_length=1, strip_whitespace=True)

_DICT_ADAPTER: TypeAdapter[JSONObject] = TypeAdapter(JSONObject)
_PARAM_SPACE_ADAPTER: TypeAdapter[list[ParameterSpec]] = TypeAdapter(list[ParameterSpec])


def _err(msg: str) -> str:
    return json.dumps({"error": msg})



def _parse_parameter_space(raw_json: str) -> list[ParameterSpec]:
    """Parse and validate the parameter space JSON array.

    Pydantic handles type coercion, field aliases, and logical constraint
    checks (min < max, step > 0) via the :class:`ParameterSpec` model.
    This function adds semantic checks that Pydantic can't express:
    non-empty list, duplicate names, and required-field-per-type rules
    (numeric needs min/max, categorical needs choices).
    """
    specs = _PARAM_SPACE_ADAPTER.validate_json(raw_json)
    if not specs:
        msg = (
            "parameter_space_json is an empty array. "
            "Provide at least one parameter to optimise."
        )
        raise ValueError(msg)
    names = [s.name for s in specs]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        msg = (
            f"Duplicate parameter names: {', '.join(sorted(dupes))}. "
            "Each parameter must have a unique name."
        )
        raise ValueError(msg)
    for s in specs:
        if s.param_type in ("numeric", "integer"):
            if s.min_value is None or s.max_value is None:
                msg = f"'{s.name}': type '{s.param_type}' requires both 'min' and 'max'"
                raise ValueError(msg)
        elif s.param_type == "categorical" and not s.choices:
            msg = f"'{s.name}': type 'categorical' requires a non-empty 'choices' array"
            raise ValueError(msg)
    return specs


def _parse_json_object(
    raw_json: str | None, default: JSONObject | None = None
) -> JSONObject | None:
    """Parse a JSON object field. Returns parsed dict or default."""
    if not raw_json:
        return default if default is not None else {}
    return _DICT_ADAPTER.validate_json(raw_json)



def _parse_and_validate_inputs(
    target: "OptimizationTarget",
    controls: "OptimizationControls",
) -> tuple[list[ParameterSpec], JSONObject, JSONObject | None]:
    """Parse JSON string fields into typed objects.

    Scalar fields (objective, method, budget, etc.) are already validated
    by Pydantic on the model classes. This function handles the JSON string
    fields that need explicit parsing.
    """
    specs = _parse_parameter_space(target.parameter_space_json)
    fixed = _parse_json_object(target.fixed_parameters_json, default={})
    controls_extra = _parse_json_object(controls.controls_extra_parameters_json)
    return specs, fixed or {}, controls_extra



class OptimizationTarget(BaseModel):
    """Target search and parameter space to optimise."""

    record_type: Annotated[str, _NONEMPTY, AIParam(desc="WDK record type (e.g. 'transcript')")]
    search_name: Annotated[
        str, _NONEMPTY, AIParam(desc="WDK search/question urlSegment to optimise")
    ]
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
    ]
    fixed_parameters_json: Annotated[
        str,
        AIParam(
            desc=(
                "JSON object of parameters held constant during optimisation. "
                'Example: {"organism":"P. falciparum 3D7","direction":"up-regulated"}'
            )
        ),
    ]


class OptimizationControls(BaseModel):
    """Control sets for scoring."""

    @model_validator(mode="after")
    def _require_at_least_one_control_set(self) -> "OptimizationControls":
        has_pos = self.positive_controls and len(self.positive_controls) > 0
        has_neg = self.negative_controls and len(self.negative_controls) > 0
        if not has_pos and not has_neg:
            msg = (
                "At least one of positive_controls or negative_controls must be "
                "provided with at least one ID."
            )
            raise ValueError(msg)
        return self

    controls_search_name: Annotated[
        str, _NONEMPTY,
        AIParam(desc="Search that accepts a list of record IDs (for controls)"),
    ]
    controls_param_name: Annotated[
        str, _NONEMPTY,
        AIParam(desc="Parameter name within controls_search_name that accepts IDs"),
    ]
    positive_controls: Annotated[
        list[str] | None,
        AIParam(desc="Known-positive IDs that should be returned"),
    ] = None
    negative_controls: Annotated[
        list[str] | None,
        AIParam(desc="Known-negative IDs that should NOT be returned"),
    ] = None
    controls_value_format: Annotated[
        ControlValueFormat,
        AIParam(desc="How to encode the control ID list (default: 'newline')"),
    ] = "newline"
    controls_extra_parameters_json: Annotated[
        str | None,
        AIParam(desc="JSON object of extra fixed parameters for the controls search"),
    ] = None
    id_field: Annotated[
        str | None,
        AIParam(desc="Optional record-id field name for answer records"),
    ] = None


class OptimizationSettings(BaseModel):
    """Optimization hyperparameters."""

    @model_validator(mode="after")
    def _validate_beta(self) -> "OptimizationSettings":
        if self.objective == "f_beta" and self.beta <= 0:
            msg = f"beta must be positive when objective is 'f_beta', got {self.beta!r}"
            raise ValueError(msg)
        return self

    budget: Annotated[
        int, AIParam(desc="Max number of trials (default 15, max 50)"),
        Field(ge=1, le=_MAX_BUDGET),
    ] = 15
    objective: Annotated[
        OptimizationObjective,
        AIParam(
            desc=(
                "Scoring objective: 'f1' (balanced, default), 'recall', "
                "'precision', 'f_beta' (specify beta), or 'custom'"
            )
        ),
    ] = "f1"
    beta: Annotated[
        float, AIParam(desc="Beta value for f_beta objective (default 1.0)")
    ] = 1.0
    method: Annotated[
        OptimizationMethod,
        AIParam(
            desc="Optimisation method: 'bayesian' (default, recommended), 'grid', or 'random'"
        ),
    ] = "bayesian"
    estimated_size_penalty: Annotated[
        float,
        AIParam(
            desc=(
                "Weight for penalising large result sets (0 = off, 0.1 = tiebreaker, "
                "higher = strongly prefer tighter results). Default 0.1."
            )
        ),
    ] = 0.1


_DEFAULT_SETTINGS = OptimizationSettings()



class OptimizationToolsMixin:
    """Kani tool mixin for search parameter optimization."""

    site_id: str = ""

    async def _emit_event(self, event: JSONObject) -> None:
        """Emit an SSE event. Override in subclass to push to streaming queue."""

    @ai_function()
    async def optimize_search_parameters(
        self,
        target: Annotated[
            OptimizationTarget, AIParam(desc="Target search to optimise")
        ],
        controls: Annotated[
            OptimizationControls, AIParam(desc="Control sets for scoring")
        ],
        settings: Annotated[
            OptimizationSettings, AIParam(desc="Optimisation hyperparameters")
        ] = _DEFAULT_SETTINGS,
    ) -> str:
        """Optimise search parameters against positive/negative control gene lists.

        Runs multiple trials, varying the parameters in `parameter_space` while
        holding `fixed_parameters` constant. Each trial evaluates the search
        against the controls and scores the result. Returns the best
        configuration, all trials, Pareto frontier, and sensitivity analysis.

        This is a long-running operation. The user will see real-time progress
        in the UI. Always confirm the plan with the user before calling this.
        """
        try:
            specs, fixed_parameters, controls_extra_parameters = (
                _parse_and_validate_inputs(target, controls)
            )
        except (ValueError, ValidationError) as exc:
            return _err(str(exc))

        opt_inp = OptimizationInput(
            site_id=self.site_id,
            record_type=target.record_type,
            search_name=target.search_name,
            fixed_parameters=fixed_parameters,
            parameter_space=specs,
            controls_search_name=controls.controls_search_name,
            controls_param_name=controls.controls_param_name,
            positive_controls=controls.positive_controls,
            negative_controls=controls.negative_controls,
            controls_value_format=controls.controls_value_format,
            controls_extra_parameters=controls_extra_parameters,
            id_field=controls.id_field,
        )
        opt_cfg = OptimizationConfig(
            budget=settings.budget,
            objective=settings.objective,
            beta=settings.beta,
            method=settings.method,
            estimated_size_penalty=max(0.0, settings.estimated_size_penalty),
        )
        return await self._run_optimization(opt_inp, opt_cfg)

    async def _run_optimization(
        self,
        inp: OptimizationInput,
        config: OptimizationConfig,
    ) -> str:
        """Execute the optimization and return JSON result."""
        cancel_event = getattr(self, "_cancel_event", None)

        result = await optimize_search_parameters(
            inp,
            config=config,
            progress_callback=self._emit_event,
            check_cancelled=(cancel_event.is_set if cancel_event is not None else None),
        )

        result_json = result_to_json(result)
        await _attach_export(result_json, inp.search_name)
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
    except OSError:
        pass
