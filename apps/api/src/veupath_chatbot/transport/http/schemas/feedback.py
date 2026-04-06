"""Request schemas for the feedback endpoint."""

from veupath_chatbot.platform.pydantic_base import CamelModel


class FeedbackRequest(CamelModel):
    """User feedback on an assistant message."""

    trace_id: str
    stream_id: str
    value: int  # 1 = positive, 0 = negative
    comment: str | None = None
