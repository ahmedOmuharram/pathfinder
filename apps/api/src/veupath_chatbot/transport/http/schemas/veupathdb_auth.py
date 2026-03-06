"""VEuPathDB auth request/response DTOs."""

from __future__ import annotations

from pydantic import BaseModel


class AuthSuccessResponse(BaseModel):
    """Success response. Auth token is set via httpOnly cookie only."""

    success: bool


class AuthStatusResponse(BaseModel):
    """Current auth status response."""

    signedIn: bool
    name: str | None = None
    email: str | None = None
