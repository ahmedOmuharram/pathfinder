"""Cross-validation endpoint for experiments."""

from __future__ import annotations

from fastapi import APIRouter

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.transport.http.deps import ExperimentDep
from veupath_chatbot.transport.http.schemas.experiments import (
    RunCrossValidationRequest,
)

router = APIRouter()


@router.post("/{experiment_id}/cross-validate")
async def run_cv(
    exp: ExperimentDep,
    request: RunCrossValidationRequest,
) -> JSONObject:
    """Run cross-validation on an existing experiment."""
    from veupath_chatbot.services.experiment.cross_validation import (
        run_cross_validation,
        run_cross_validation_tree,
    )
    from veupath_chatbot.services.experiment.types import cv_result_to_json

    is_tree_mode = exp.config.mode != "single" and isinstance(
        exp.config.step_tree, dict
    )

    if is_tree_mode:
        cv = await run_cross_validation_tree(
            site_id=exp.config.site_id,
            record_type=exp.config.record_type,
            tree=exp.config.step_tree,
            controls_search_name=exp.config.controls_search_name,
            controls_param_name=exp.config.controls_param_name,
            controls_value_format=exp.config.controls_value_format,
            positive_controls=exp.config.positive_controls,
            negative_controls=exp.config.negative_controls,
            k=request.k_folds,
            full_metrics=exp.metrics,
        )
    else:
        cv = await run_cross_validation(
            site_id=exp.config.site_id,
            record_type=exp.config.record_type,
            search_name=exp.config.search_name,
            parameters=exp.config.parameters,
            controls_search_name=exp.config.controls_search_name,
            controls_param_name=exp.config.controls_param_name,
            positive_controls=exp.config.positive_controls,
            negative_controls=exp.config.negative_controls,
            controls_value_format=exp.config.controls_value_format,
            k=request.k_folds,
            full_metrics=exp.metrics,
        )

    exp.cross_validation = cv
    get_experiment_store().save(exp)
    return cv_result_to_json(cv)
