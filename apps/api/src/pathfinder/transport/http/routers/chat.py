from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from pathfinder.ai.conversation.dispatcher import dispatch
from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.services import quota as quota_service
from pathfinder.transport.http.deps import CurrentUser, DBSession

router = APIRouter(tags=["chat"])


@router.post("/api/v1/chat")
async def chat(
    body: ChatRequestBody,
    session: DBSession,
    user_id: CurrentUser,
) -> Response:
    quota = await quota_service.check_allowed(session, user_id)
    if quota.used_usd >= quota.limit_usd:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "monthly_quota_exhausted",
                "usedUsd": str(quota.used_usd),
                "limitUsd": str(quota.limit_usd),
                "resetsAt": quota.resets_at.isoformat(),
                "totalTokens": quota.total_tokens,
            },
        )
    return await dispatch(body=body, session=session, user_id=user_id)
