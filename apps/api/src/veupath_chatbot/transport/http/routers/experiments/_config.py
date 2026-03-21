"""Build ExperimentConfig from HTTP request DTOs.

This is a transport-layer adapter: it converts the HTTP-specific
``CreateExperimentRequest`` Pydantic model into the service-layer
``ExperimentConfig`` dataclass.  Lives here (not in services/) because
it depends on transport schemas.
"""

from veupath_chatbot.services.experiment.types import ExperimentConfig
from veupath_chatbot.transport.http.schemas.experiments import CreateExperimentRequest


def config_from_request(req: CreateExperimentRequest) -> ExperimentConfig:
    """Build :class:`ExperimentConfig` from a create request DTO.

    Both models share identical Python field names, so ``model_validate``
    handles the bulk conversion.  Only a handful of edge cases need
    explicit handling:

    * ``optimization_objective``: request defaults to ``None`` →
      pop so ExperimentConfig's ``"balanced_accuracy"`` default applies.
    * ``step_analysis_phases``: same pattern (``None`` → default list).
    * ``parameter_display_values``: stringify keys and values.
    * ``optimization_specs`` / ``threshold_knobs`` / ``operator_knobs``:
      empty/falsy → ``None``.
    """
    data = req.model_dump()

    # Coalesce None/falsy → pop so ExperimentConfig defaults apply.
    for field in ("optimization_objective", "step_analysis_phases"):
        if not data.get(field):
            data.pop(field, None)

    # Stringify parameter_display_values.
    pdv = data.get("parameter_display_values")
    if isinstance(pdv, dict):
        data["parameter_display_values"] = {str(k): str(v) for k, v in pdv.items()}

    # Empty/falsy nested lists → None.
    for field in ("optimization_specs", "threshold_knobs", "operator_knobs"):
        if not data.get(field):
            data[field] = None

    return ExperimentConfig.model_validate(data)
