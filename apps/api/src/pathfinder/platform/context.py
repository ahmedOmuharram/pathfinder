"""Context variables for request-scoped data."""

from contextvars import ContextVar
from uuid import UUID

from pathfinder.platform.principal import DEFAULT_APPLICATION_ID

# Request ID for tracing
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Current user ID
user_id_ctx: ContextVar[UUID | None] = ContextVar("user_id", default=None)

# Application the request is made on behalf of
application_id_ctx: ContextVar[str] = ContextVar(
    "application_id", default=DEFAULT_APPLICATION_ID
)


def calling_application() -> str:
    """The application the current request or worker job acts as."""
    return application_id_ctx.get()


# Current site context
site_id_ctx: ContextVar[str | None] = ContextVar("site_id", default=None)

# VEuPathDB auth token (from request cookies/headers)
veupathdb_auth_token_ctx: ContextVar[str | None] = ContextVar(
    "veupathdb_auth_token", default=None
)

# Request base URL (e.g. "http://localhost:3000") for constructing full download URLs.
# Set from the Origin or Referer header so export URLs resolve correctly for the user.
request_base_url_ctx: ContextVar[str | None] = ContextVar(
    "request_base_url", default=None
)

# Conversation stream identity (set by the chat orchestrator).
stream_id_ctx: ContextVar[str | None] = ContextVar("stream_id", default=None)

# Active operation identity (set by the chat orchestrator).
operation_id_ctx: ContextVar[str | None] = ContextVar("operation_id", default=None)
