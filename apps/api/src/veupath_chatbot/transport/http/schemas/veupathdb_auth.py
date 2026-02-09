"""VEuPathDB auth request/response DTOs."""

from __future__ import annotations

from pydantic import BaseModel


class AuthSuccessResponse(BaseModel):
    """Success response, optionally carrying the internal auth token."""

    success: bool
    authToken: str | None = None


class AuthStatusResponse(BaseModel):
    """Current auth status response."""

    signedIn: bool
    name: str | None = None
    email: str | None = None
