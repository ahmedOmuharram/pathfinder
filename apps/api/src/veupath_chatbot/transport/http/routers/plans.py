"""Plan session endpoints (planning mode workspace)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Query

from veupath_chatbot.platform.errors import ErrorCode, NotFoundError, ValidationError
from veupath_chatbot.transport.http.deps import CurrentUser, PlanSessionRepo
from veupath_chatbot.transport.http.schemas import (
    MessageResponse,
    OpenPlanSessionRequest,
    OpenPlanSessionResponse,
    PlanSessionResponse,
    PlanSessionSummaryResponse,
    ThinkingResponse,
    UpdatePlanSessionRequest,
)

router = APIRouter(prefix="/api/v1/plans", tags=["plans"])


@router.get("", response_model=list[PlanSessionSummaryResponse])
async def list_plans(
    plan_repo: PlanSessionRepo,
    user_id: CurrentUser,
    site_id: str | None = Query(default=None, alias="siteId"),
) -> list[PlanSessionSummaryResponse]:
    sessions = await plan_repo.list_by_user(user_id, site_id)
    # Hide unused (empty) plan sessions from the sidebar.
    sessions = [
        s for s in sessions if isinstance(s.messages, list) and len(s.messages) > 0
    ]
    now = datetime.now(UTC)
    return [
        PlanSessionSummaryResponse(
            id=s.id,
            siteId=s.site_id,
            title=s.title,
            createdAt=s.created_at or now,
            updatedAt=s.updated_at or s.created_at or now,
        )
        for s in sessions
    ]


@router.post("/open", response_model=OpenPlanSessionResponse)
async def open_plan(
    request: OpenPlanSessionRequest,
    plan_repo: PlanSessionRepo,
    user_id: CurrentUser,
) -> OpenPlanSessionResponse:
    if request.plan_session_id:
        existing = await plan_repo.get_by_id_for_user(
            plan_session_id=request.plan_session_id, user_id=user_id
        )
        if existing:
            return OpenPlanSessionResponse(planSessionId=existing.id)
    created = await plan_repo.create(
        user_id=user_id,
        site_id=request.site_id,
        title=request.title or "New Conversation",
        plan_session_id=request.plan_session_id,
    )
    return OpenPlanSessionResponse(planSessionId=created.id)


@router.get("/{planSessionId:uuid}", response_model=PlanSessionResponse)
async def get_plan(
    planSessionId: UUID, plan_repo: PlanSessionRepo, user_id: CurrentUser
) -> PlanSessionResponse:
    ps = await plan_repo.get_by_id_for_user(
        plan_session_id=planSessionId, user_id=user_id
    )
    if not ps:
        raise NotFoundError(code=ErrorCode.NOT_FOUND, title="Plan session not found")
    now = datetime.now(UTC)

    # Always return a list for messages (empty plan sessions should serialize as []).
    messages: list[MessageResponse] = []
    if isinstance(ps.messages, list):
        for msg in ps.messages:
            try:
                messages.append(MessageResponse.model_validate(msg))
            except Exception:
                # Tolerate malformed persisted messages rather than 500'ing.
                continue

    # Convert JSONObject to ThinkingResponse
    thinking: ThinkingResponse | None = None
    if isinstance(ps.thinking, dict) and ps.thinking:
        try:
            thinking = ThinkingResponse.model_validate(ps.thinking)
        except Exception:
            thinking = None

    return PlanSessionResponse(
        id=ps.id,
        siteId=ps.site_id,
        title=ps.title,
        messages=messages,
        thinking=thinking,
        planningArtifacts=ps.planning_artifacts,
        modelId=ps.model_id,
        createdAt=ps.created_at or now,
        updatedAt=ps.updated_at or ps.created_at or now,
    )


@router.delete("/{planSessionId:uuid}")
async def delete_plan(
    planSessionId: UUID, plan_repo: PlanSessionRepo, user_id: CurrentUser
) -> dict[str, bool]:
    deleted = await plan_repo.delete(plan_session_id=planSessionId, user_id=user_id)
    if not deleted:
        raise NotFoundError(code=ErrorCode.NOT_FOUND, title="Plan session not found")
    return {"success": True}


@router.patch("/{planSessionId:uuid}", response_model=PlanSessionSummaryResponse)
async def update_plan(
    planSessionId: UUID,
    request: UpdatePlanSessionRequest,
    plan_repo: PlanSessionRepo,
    user_id: CurrentUser,
) -> PlanSessionSummaryResponse:
    if request.title is None:
        raise ValidationError(title="No updates provided")
    updated = await plan_repo.update_title(
        plan_session_id=planSessionId, user_id=user_id, title=request.title
    )
    if not updated:
        raise NotFoundError(code=ErrorCode.NOT_FOUND, title="Plan session not found")
    now = datetime.now(UTC)
    return PlanSessionSummaryResponse(
        id=updated.id,
        siteId=updated.site_id,
        title=updated.title,
        createdAt=updated.created_at or now,
        updatedAt=updated.updated_at or updated.created_at or now,
    )
