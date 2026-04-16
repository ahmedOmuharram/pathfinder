from fastapi import APIRouter
from shared_py.stream_events import StreamEvent

router = APIRouter(tags=["internal-schema"])


@router.post(
    "/internal/schema/stream-event",
    response_model=StreamEvent,
    include_in_schema=True,
)
async def _schema_stream_event() -> StreamEvent:  # pragma: no cover
    msg = "schema-only endpoint"
    raise NotImplementedError(msg)
