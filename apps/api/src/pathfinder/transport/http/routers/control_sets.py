"""CRUD endpoints for reusable control gene sets."""

from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import Field

from pathfinder.persistence.models import ControlSet
from pathfinder.persistence.repositories.control_set import ControlSetCreate
from pathfinder.platform.errors import NotFoundError
from pathfinder.platform.errors import ValidationError as CoreValidationError
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.uuid_utils import format_uuid
from pathfinder.transport.http.deps import ControlSetRepo, CurrentUser

router = APIRouter(prefix="/api/v1/control-sets", tags=["control-sets"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


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


class ControlSetResponse(CamelModel):
    """Serialized control set returned to the client."""

    id: str
    name: str
    site_id: str
    record_type: str
    positive_ids: list[str]
    negative_ids: list[str]
    source: str | None = None
    tags: list[str]
    provenance_notes: str | None = Field(None)
    version: int
    is_public: bool
    user_id: str | None = Field(None)
    created_at: str


def _serialize(cs: ControlSet) -> ControlSetResponse:
    """Convert an ORM ``ControlSet`` to a response model."""
    return ControlSetResponse(
        id=str(cs.id),
        name=cs.name,
        site_id=cs.site_id,
        record_type=cs.record_type,
        positive_ids=[str(x) for x in (cs.positive_ids or [])],
        negative_ids=[str(x) for x in (cs.negative_ids or [])],
        source=cs.source,
        tags=[str(x) for x in (cs.tags or [])],
        provenance_notes=cs.provenance_notes,
        version=cs.version,
        is_public=cs.is_public,
        user_id=format_uuid(cs.user_id),
        created_at=cs.created_at.isoformat() if cs.created_at else "",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ControlSetResponse])
async def list_control_sets(
    repo: ControlSetRepo,
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
    rows = await repo.list_by_site(
        site_id=site_id,
        user_id=user_id,
        tags=tag_list,
    )
    return [_serialize(r) for r in rows]


@router.get("/{control_set_id}", response_model=ControlSetResponse)
async def get_control_set(
    control_set_id: str,
    repo: ControlSetRepo,
    user_id: CurrentUser,
) -> ControlSetResponse:
    """Get a single control set by ID."""
    cs = await repo.get_by_id(UUID(control_set_id))
    if cs is None:
        raise NotFoundError(title="Control set not found")
    if not cs.is_public and cs.user_id != user_id:
        raise NotFoundError(title="Control set not found")
    return _serialize(cs)


@router.post("", response_model=ControlSetResponse, status_code=201)
async def create_control_set(
    body: CreateControlSetRequest,
    repo: ControlSetRepo,
    user_id: CurrentUser,
) -> ControlSetResponse:
    """Create a new control set."""
    cs = await repo.create(
        ControlSetCreate(
            name=body.name,
            site_id=body.site_id,
            record_type=body.record_type,
            positive_ids=body.positive_ids,
            negative_ids=body.negative_ids,
            source=body.source,
            tags=body.tags or [],
            provenance_notes=body.provenance_notes,
            is_public=body.is_public,
            user_id=user_id,
        )
    )
    return _serialize(cs)


@router.delete("/{control_set_id}", status_code=204)
async def delete_control_set(
    control_set_id: str,
    repo: ControlSetRepo,
    user_id: CurrentUser,
) -> None:
    """Delete a control set owned by the current user."""
    cs = await repo.get_by_id(UUID(control_set_id))
    if cs is None or cs.user_id != user_id:
        raise NotFoundError(title="Control set not found")
    await repo.delete(UUID(control_set_id))
