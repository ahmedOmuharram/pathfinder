"""VEuPathDB auth request/response DTOs."""

from __future__ import annotations

from pydantic import BaseModel


class AuthSuccessResponse(BaseModel):
    """Simple success response."""

    success: bool


class AuthStatusResponse(BaseModel):
    """Current auth status response."""

    signedIn: bool
    name: str | None = None
    email: str | None = None
