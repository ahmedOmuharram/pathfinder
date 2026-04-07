"""User feedback endpoint — records thumbs up/down in Langfuse."""

from fastapi import APIRouter, Response
from starlette.requests import Request

from veupath_chatbot.platform.langfuse.feedback import record_feedback
from veupath_chatbot.platform.security import limiter
from veupath_chatbot.transport.http.schemas.feedback import FeedbackRequest

router = APIRouter(prefix="/api/v1", tags=["feedback"])


@router.post("/feedback", status_code=204, response_class=Response)
@limiter.limit("30/minute")
async def submit_feedback(request: Request, body: FeedbackRequest) -> Response:
    """Record user feedback on an assistant response."""
    record_feedback(
        trace_id=body.trace_id,
        stream_id=body.stream_id,
        value=body.value,
        comment=body.comment,
    )
    return Response(status_code=204)
