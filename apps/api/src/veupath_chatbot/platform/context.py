"""Context variables for request-scoped data."""

from contextvars import ContextVar
from uuid import UUID

# Request ID for tracing
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Current user ID
user_id_ctx: ContextVar[UUID | None] = ContextVar("user_id", default=None)

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
