"""CRUD endpoints for experiments: list, get, update, delete."""

from fastapi import APIRouter, Depends, Response
from pydantic import Field

from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject
from pathfinder.services.experiment.materialization import (
    cleanup_experiment_strategy,
)
from pathfinder.services.experiment.store import get_experiment_store
from pathfinder.services.experiment.types import (
    experiment_summary_to_json,
    experiment_to_json,
)
from pathfinder.transport.http.deps import (
    CurrentUser,
    ExperimentDep,
    SiteIdQuery,
    require_registered_wdk_identity,
)

router = APIRouter()


# -- Non-parametric routes (must be defined before /{experiment_id}) ----------


class PatchExperimentRequest(CamelModel):
    """Request body for PATCH /experiments/{experiment_id}."""

    notes: str | None = Field(default=None, max_length=5000)


# -- Parametric routes -------------------------------------------------------


@router.get("/")
async def list_experiments(
    user_id: CurrentUser,
    siteId: SiteIdQuery = None,
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


# Deleting an experiment deletes the WDK strategy it materialized.
@router.delete(
    "/{experiment_id}",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(require_registered_wdk_identity)],
)
async def delete_experiment(exp: ExperimentDep, user_id: CurrentUser) -> Response:
    """Delete an experiment and clean up its WDK strategy."""
    await cleanup_experiment_strategy(exp)

    store = get_experiment_store()
    await store.adelete(exp.id)
    return Response(status_code=204)
