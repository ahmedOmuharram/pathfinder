"""Context variables the science owns. The runtime owns the rest."""

from contextvars import ContextVar

# VEuPathDB auth token (from request cookies/headers)
veupathdb_auth_token_ctx: ContextVar[str | None] = ContextVar(
    "veupathdb_auth_token", default=None
)

# Request base URL (e.g. "http://localhost:3000") for constructing full download URLs.
# Set from the Origin or Referer header so export URLs resolve correctly for the user.
request_base_url_ctx: ContextVar[str | None] = ContextVar(
    "request_base_url", default=None
)
