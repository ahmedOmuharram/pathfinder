"""CRUD endpoints for reusable control gene sets."""

from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import Field

from pathfinder.platform.errors import ValidationError as CoreValidationError
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.control_sets import (
    ControlSetResponse,
    ControlSetService,
    NewControlSet,
)
from pathfinder.transport.http.deps import CurrentUser, DBSession

router = APIRouter(prefix="/api/v1/control-sets", tags=["control-sets"])


class CreateControlSetRequest(CamelModel):
    """Payload for creating a new control set."""

    name: str
    site_id: str
    record_type: str
    positive_ids: list[str] = Field(default_factory=list)
    negative_ids: list[str] = Field(default_factory=list)
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    provenance_notes: str | None = Field(None)
    is_public: bool = Field(default=False)


@router.get("", response_model=list[ControlSetResponse])
async def list_control_sets(
    session: DBSession,
    user_id: CurrentUser,
    site_id: str | None = Query(None, alias="siteId"),
    tags: str | None = None,
) -> list[ControlSetResponse]:
    """List control sets visible to the current user."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    if not site_id:
        raise CoreValidationError(
            title="Missing required parameter",
            detail="siteId query parameter is required",
        )
    return await ControlSetService(session).list_for_site(
        site_id=site_id,
        user_id=user_id,
        tags=tag_list,
    )


@router.get("/{control_set_id}", response_model=ControlSetResponse)
async def get_control_set(
    control_set_id: str,
    session: DBSession,
    user_id: CurrentUser,
) -> ControlSetResponse:
    """Get a single control set by ID."""
    return await ControlSetService(session).get(UUID(control_set_id), user_id)


@router.post("", response_model=ControlSetResponse, status_code=201)
async def create_control_set(
    body: CreateControlSetRequest,
    session: DBSession,
    user_id: CurrentUser,
) -> ControlSetResponse:
    """Create a new control set."""
    spec = NewControlSet(
        name=body.name,
        site_id=body.site_id,
        record_type=body.record_type,
        positive_ids=body.positive_ids,
        negative_ids=body.negative_ids,
        source=body.source,
        tags=body.tags,
        provenance_notes=body.provenance_notes,
        is_public=body.is_public,
    )
    return await ControlSetService(session).create(spec, user_id=user_id)


@router.delete("/{control_set_id}", status_code=204)
async def delete_control_set(
    control_set_id: str,
    session: DBSession,
    user_id: CurrentUser,
) -> None:
    """Delete a control set owned by the current user."""
    await ControlSetService(session).delete(UUID(control_set_id), user_id)
