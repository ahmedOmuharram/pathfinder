"""Cross-validation endpoint for experiments."""

from typing import cast

from fastapi import APIRouter

from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.cross_validation import (
    CrossValidationOptions,
    run_cross_validation,
)
from veupath_chatbot.services.experiment.helpers import ControlsContext
from veupath_chatbot.services.experiment.store import get_experiment_store
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
    ctx = ControlsContext.from_config(exp.config)
    try:
        cv = await run_cross_validation(
            ctx,
            tree=(
                exp.config.step_tree if isinstance(exp.config.step_tree, dict) else None
            ),
            search_name=exp.config.search_name if not exp.config.is_tree_mode else None,
            parameters=exp.config.parameters if not exp.config.is_tree_mode else None,
            options=CrossValidationOptions(
                k=request.k_folds,
                full_metrics=exp.metrics,
            ),
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
    return cast("JSONObject", cv.model_dump(by_alias=True))
