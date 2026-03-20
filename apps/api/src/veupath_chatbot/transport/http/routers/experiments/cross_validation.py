"""Cross-validation endpoint for experiments."""

from typing import cast

from fastapi import APIRouter

from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.cross_validation import (
    run_cross_validation,
)
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import to_json
from veupath_chatbot.transport.http.deps import CurrentUser, ExperimentDep
from veupath_chatbot.transport.http.schemas.experiments import (
    RunCrossValidationRequest,
)

router = APIRouter()
logger = get_logger(__name__)


@router.post("/{experiment_id}/cross-validate")
async def run_cv(
    exp: ExperimentDep,
    request: RunCrossValidationRequest,
    user_id: CurrentUser,
) -> JSONObject:
    """Run cross-validation on an existing experiment."""
    try:
        cv = await run_cross_validation(
            site_id=exp.config.site_id,
            record_type=exp.config.record_type,
            controls_search_name=exp.config.controls_search_name,
            controls_param_name=exp.config.controls_param_name,
            controls_value_format=exp.config.controls_value_format,
            positive_controls=exp.config.positive_controls,
            negative_controls=exp.config.negative_controls,
            tree=(
                exp.config.step_tree if isinstance(exp.config.step_tree, dict) else None
            ),
            search_name=exp.config.search_name if not exp.config.is_tree_mode else None,
            parameters=exp.config.parameters if not exp.config.is_tree_mode else None,
            k=request.k_folds,
            full_metrics=exp.metrics,
        )
    except WDKError:
        raise
    except Exception as exc:
        logger.error(
            "Cross-validation failed",
            experiment_id=exp.id,
            error=str(exc),
            exc_info=True,
        )
        msg = f"Cross-validation failed: {exc}"
        raise WDKError(msg) from exc

    exp.cross_validation = cv
    get_experiment_store().save(exp)
    return cast("JSONObject", to_json(cv))
