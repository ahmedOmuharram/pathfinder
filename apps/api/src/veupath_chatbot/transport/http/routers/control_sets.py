"""CRUD endpoints for reusable control gene sets."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from veupath_chatbot.persistence.models import ControlSet
from veupath_chatbot.transport.http.deps import ControlSetRepo, CurrentUser

router = APIRouter(prefix="/api/v1/control-sets", tags=["control-sets"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateControlSetRequest(BaseModel):
    """Payload for creating a new control set."""

    name: str
    site_id: str = Field(alias="siteId")
    record_type: str = Field(alias="recordType")
    positive_ids: list[str] = Field(alias="positiveIds", default_factory=list)
    negative_ids: list[str] = Field(alias="negativeIds", default_factory=list)
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    provenance_notes: str | None = Field(None, alias="provenanceNotes")
    is_public: bool = Field(False, alias="isPublic")

    model_config = {"populate_by_name": True}


class ControlSetResponse(BaseModel):
    """Serialized control set returned to the client."""

    id: str
    name: str
    site_id: str = Field(alias="siteId")
    record_type: str = Field(alias="recordType")
    positive_ids: list[str] = Field(alias="positiveIds")
    negative_ids: list[str] = Field(alias="negativeIds")
    source: str | None = None
    tags: list[str]
    provenance_notes: str | None = Field(None, alias="provenanceNotes")
    version: int
    is_public: bool = Field(alias="isPublic")
    user_id: str | None = Field(None, alias="userId")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


def _serialize(cs: ControlSet) -> ControlSetResponse:
    """Convert an ORM ``ControlSet`` to a response model."""
    return ControlSetResponse(
        id=str(cs.id),
        name=cs.name,
        siteId=cs.site_id,
        recordType=cs.record_type,
        positiveIds=[str(x) for x in (cs.positive_ids or [])],
        negativeIds=[str(x) for x in (cs.negative_ids or [])],
        source=cs.source,
        tags=[str(x) for x in (cs.tags or [])],
        provenanceNotes=cs.provenance_notes,
        version=cs.version,
        isPublic=cs.is_public,
        userId=str(cs.user_id) if cs.user_id else None,
        createdAt=cs.created_at.isoformat() if cs.created_at else "",
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
        raise HTTPException(
            status_code=400, detail="siteId query parameter is required"
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
        raise HTTPException(status_code=404, detail="Control set not found")
    return _serialize(cs)


@router.post("", response_model=ControlSetResponse, status_code=201)
async def create_control_set(
    body: CreateControlSetRequest,
    repo: ControlSetRepo,
    user_id: CurrentUser,
) -> ControlSetResponse:
    """Create a new control set."""
    cs = await repo.create(
        name=body.name,
        site_id=body.site_id,
        record_type=body.record_type,
        positive_ids=body.positive_ids,
        negative_ids=body.negative_ids,
        source=body.source,
        tags=body.tags,
        provenance_notes=body.provenance_notes,
        is_public=body.is_public,
        user_id=user_id,
    )
    return _serialize(cs)


@router.delete("/{control_set_id}", status_code=204)
async def delete_control_set(
    control_set_id: str,
    repo: ControlSetRepo,
    user_id: CurrentUser,
) -> None:
    """Delete a control set."""
    deleted = await repo.delete(UUID(control_set_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Control set not found")
