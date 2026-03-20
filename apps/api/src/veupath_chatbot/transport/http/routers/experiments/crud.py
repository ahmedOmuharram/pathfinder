"""CRUD endpoints for experiments: list, get, update, delete."""

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.materialization import (
    cleanup_experiment_strategy,
)
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    experiment_summary_to_json,
    experiment_to_json,
)
from veupath_chatbot.transport.http.deps import CurrentUser, ExperimentDep

router = APIRouter()


# -- Non-parametric routes (must be defined before /{experiment_id}) ----------


class PatchExperimentRequest(BaseModel):
    """Request body for PATCH /experiments/{experiment_id}."""

    notes: str | None = Field(default=None, max_length=5000)

    model_config = {"populate_by_name": True}


# -- Parametric routes -------------------------------------------------------


@router.get("/")
async def list_experiments(
    user_id: CurrentUser,
    siteId: str | None = None,
) -> list[JSONObject]:
    """List experiments owned by the current user, optionally filtered by site."""
    store = get_experiment_store()
    experiments = await store.alist_all(site_id=siteId, user_id=str(user_id))
    return [experiment_summary_to_json(e) for e in experiments]


@router.get("/{experiment_id}")
async def get_experiment(exp: ExperimentDep, user_id: CurrentUser) -> JSONObject:
    """Get full experiment details including all results."""
    return experiment_to_json(exp)


@router.patch("/{experiment_id}")
async def update_experiment(
    exp: ExperimentDep,
    body: PatchExperimentRequest,
    user_id: CurrentUser,
) -> JSONObject:
    """Update experiment metadata (e.g. notes)."""
    exp.notes = body.notes

    store = get_experiment_store()
    store.save(exp)
    return experiment_to_json(exp)


@router.delete("/{experiment_id}", status_code=204, response_class=Response)
async def delete_experiment(exp: ExperimentDep, user_id: CurrentUser) -> Response:
    """Delete an experiment and clean up its WDK strategy."""
    await cleanup_experiment_strategy(exp)

    store = get_experiment_store()
    await store.adelete(exp.id)
    return Response(status_code=204)
