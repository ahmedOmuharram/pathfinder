"""VEuPathDB auth request/response DTOs."""

from pathfinder.platform.pydantic_base import CamelModel


class AuthSuccessResponse(CamelModel):
    """Success response. Auth token is set via httpOnly cookie only."""

    success: bool


class AuthStatusResponse(CamelModel):
    """Current auth status response."""

    signedIn: bool
    name: str | None = None
    email: str | None = None
