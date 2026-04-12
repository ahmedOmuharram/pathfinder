"""Structured plan-action routes for interactive plan control events."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pathfinder.domain.strategy.plan import PlanStatus
from pathfinder.domain.strategy.plan_actions import (
    PlanActionContext,
    apply_plan_approval,
)
from pathfinder.persistence.repositories import PlanRepository
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.event_schemas_pipeline import PlanApprovedEventData
from pathfinder.platform.events import emit
from pathfinder.platform.langfuse.actions import (
    ProductActionEvent,
    record_product_action,
)
from pathfinder.platform.redis import get_redis
from pathfinder.platform.security import limiter
from pathfinder.services.chat.orchestrator import start_plan_action_stream
from pathfinder.services.chat.types import ChatContext, ChatTurnConfig
from pathfinder.transport.http.deps import CurrentUser, StreamRepo, UserRepo
from pathfinder.transport.http.routers._authz import get_owned_projection_or_404
from pathfinder.transport.http.schemas import (
    PlanActionOperationResponse,
    PlanActionRequest,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


@router.post("/{strategy_id}/plan-actions", status_code=202)
@limiter.limit("60/minute")
async def submit_plan_action(
    request: Request,
    strategy_id: UUID,
    body: PlanActionRequest,
    user_repo: UserRepo,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> JSONResponse:
    """Handle a structured plan action without creating a chat turn."""
    del request
    projection = await get_owned_projection_or_404(stream_repo, strategy_id, user_id)
    plan_repo = PlanRepository(stream_repo.session)
    active_plan = await plan_repo.get_active_plan(strategy_id)
    if active_plan is None:
        raise ValidationError(
            title="No active plan",
            detail="This strategy does not have a presented plan to act on.",
        )
    if active_plan.id != body.plan_id:
        raise ValidationError(
            title="Plan mismatch",
            detail="The provided planId does not match the active plan.",
        )
    if active_plan.status != PlanStatus.PRESENTED:
        raise ValidationError(
            title="Plan is not awaiting approval",
            detail="Only presented plans can be approved for execution.",
        )
    if body.action != "approve":
        raise ValidationError(
            title="Unsupported plan action",
            detail="Only the approve action is supported by this route today.",
        )

    presented_at = active_plan.updated_at
    approved_plan = apply_plan_approval(
        active_plan,
        param_edits=body.param_edits,
        answers=body.answers,
    )
    await plan_repo.save_plan(approved_plan, strategy_id)

    context = ChatContext(
        user_id=user_id,
        user_repo=user_repo,
        stream_repo=stream_repo,
    )
    config = ChatTurnConfig(
        plan_action=PlanActionContext(
            action=body.action,
            plan_id=approved_plan.id,
            source_trace_id=body.trace_id,
            source_message_group_id=body.message_group_id,
            source=body.source,
            answered_question_ids=[answer.question_id for answer in body.answers],
            edited_params=[
                f"{edit.step_id}.{edit.param_name}"
                for edit in body.param_edits
            ],
            presented_at=presented_at,
            approved_at=approved_plan.updated_at,
            approval_wait_ms=round(
                (approved_plan.updated_at - presented_at).total_seconds() * 1000
            ),
        )
    )

    operation_id, strategy_id_str = await start_plan_action_stream(
        site_id=projection.stream.site_id if projection.stream else projection.site_id,
        strategy_id=strategy_id,
        context=context,
        config=config,
    )
    record_product_action(
        ProductActionEvent(
            action="plan_approve",
            trace_id=body.trace_id,
            stream_id=strategy_id_str,
            strategy_id=strategy_id_str,
            plan_id=approved_plan.id,
            message_group_id=body.message_group_id,
            operation_id=operation_id,
            metadata={
                "source": body.source,
                "answer_count": len(body.answers),
                "param_edit_count": len(body.param_edits),
            },
        )
    )

    await emit(
        get_redis(),
        strategy_id_str,
        operation_id,
        "plan_approved",
        PlanApprovedEventData(
            plan_id=approved_plan.id,
            plan=approved_plan.model_dump(by_alias=True, mode="json"),
        ).model_dump(by_alias=True),
        session=stream_repo.session,
    )
    await stream_repo.session.commit()

    response = PlanActionOperationResponse(
        operation_id=operation_id,
        strategy_id=UUID(strategy_id_str),
    )
    return JSONResponse(
        response.model_dump(by_alias=True, mode="json"),
        status_code=202,
    )
