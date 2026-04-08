"""Optimization tool response models and helpers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.export import get_export_service
from pathfinder.services.parameter_optimization.config import ParameterSpec

logger = get_logger(__name__)


class OptimizationTarget(BaseModel):
    """Target search to optimize."""

    model_config = ConfigDict(populate_by_name=True)

    site_id: str = ""
    record_type: str = "transcript"
    search_name: str
    fixed_parameters: dict[str, str] = Field(default_factory=dict)
    parameter_space: list[dict[str, object]] = Field(default_factory=list)


class OptimizationControls(BaseModel):
    """Control sets for scoring optimization trials."""

    model_config = ConfigDict(populate_by_name=True)

    positive_controls: list[str] = Field(default_factory=list)
    negative_controls: list[str] = Field(default_factory=list)
    controls_search_name: str = "GeneByLocusTag"
    controls_param_name: str = "ds_gene_ids"
    controls_value_format: str = "newline"
    controls_extra_parameters: dict[str, str] = Field(default_factory=dict)
    id_field: str = "primary_key"


class OptimizationSettings(BaseModel):
    """Hyperparameters for optimization."""

    budget: int = 30
    objective: str = "f1"
    beta: float = 1.0
    method: str = "bayesian"
    estimated_size_penalty: float = 0.0


def _parse_and_validate_inputs(
    target: OptimizationTarget,
    controls: OptimizationControls,
) -> tuple[list[ParameterSpec], dict[str, str], dict[str, str]]:
    """Parse and validate optimization inputs, returning specs and fixed params."""
    specs = [ParameterSpec.model_validate(raw) for raw in target.parameter_space]
    if not specs:
        msg = "parameter_space must contain at least one parameter specification."
        raise ValueError(msg)
    fixed_parameters = dict(target.fixed_parameters)
    controls_extra = dict(controls.controls_extra_parameters)
    return specs, fixed_parameters, controls_extra


async def _attach_export(result_json: JSONObject, search_name: str) -> None:
    """Attach export download links to an optimization result."""
    try:
        svc = get_export_service()
        export = await svc.export_json(result_json, f"{search_name}_optimization")
        result_json["downloads"] = {
            "jsonUrl": export.url,
            "expiresInSeconds": export.expires_in_seconds,
        }
    except (AppError, OSError) as e:
        logger.warning("Optimization export failed", error=str(e))
