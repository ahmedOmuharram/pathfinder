"""Typed error model with problem+json responses."""

from enum import StrEnum

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from veupath_chatbot.platform.types import JSONArray


class ErrorCode(StrEnum):
    """Application error codes."""

    # General
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"

    # VEuPathDB
    SITE_NOT_FOUND = "SITE_NOT_FOUND"
    SEARCH_NOT_FOUND = "SEARCH_NOT_FOUND"
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    WDK_ERROR = "WDK_ERROR"

    # Strategy
    STRATEGY_NOT_FOUND = "STRATEGY_NOT_FOUND"
    INVALID_STRATEGY = "INVALID_STRATEGY"
    STEP_NOT_FOUND = "STEP_NOT_FOUND"
    INCOMPATIBLE_STEPS = "INCOMPATIBLE_STEPS"

    # Conversation
    CONVERSATION_NOT_FOUND = "CONVERSATION_NOT_FOUND"


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details response."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    code: ErrorCode
    errors: JSONArray | None = None


class AppError(Exception):
    """Base application error."""

    def __init__(
        self,
        code: ErrorCode,
        title: str,
        status: int = 400,
        detail: str | None = None,
        errors: JSONArray | None = None,
    ) -> None:
        self.code = code
        self.title = title
        self.status = status
        self.detail = detail
        self.errors = errors
        super().__init__(title)


class InternalError(AppError):
    """Internal server error (unexpected invariant failure)."""

    def __init__(
        self,
        title: str = "Internal error",
        detail: str | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.INTERNAL_ERROR,
            title=title,
            status=500,
            detail=detail,
        )


class NotFoundError(AppError):
    """Resource not found error."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.NOT_FOUND,
        title: str = "Resource not found",
        detail: str | None = None,
    ) -> None:
        super().__init__(code=code, title=title, status=404, detail=detail)


class UnauthorizedError(AppError):
    """Unauthorized error."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.UNAUTHORIZED,
        title: str = "Unauthorized",
        detail: str | None = None,
    ) -> None:
        super().__init__(code=code, title=title, status=401, detail=detail)


class ForbiddenError(AppError):
    """Forbidden error."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.FORBIDDEN,
        title: str = "Forbidden",
        detail: str | None = None,
    ) -> None:
        super().__init__(code=code, title=title, status=403, detail=detail)


class RateLimitedError(AppError):
    """Rate limited error."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.RATE_LIMITED,
        title: str = "Rate limit exceeded",
        detail: str | None = None,
    ) -> None:
        super().__init__(code=code, title=title, status=429, detail=detail)


class ValidationError(AppError):
    """Validation error."""

    def __init__(
        self,
        title: str = "Validation failed",
        detail: str | None = None,
        errors: JSONArray | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            title=title,
            status=422,
            detail=detail,
            errors=errors,
        )


class WDKError(AppError):
    """Error from VEuPathDB WDK service."""

    def __init__(self, detail: str, status: int = 502) -> None:
        super().__init__(
            code=ErrorCode.WDK_ERROR,
            title="VEuPathDB service error",
            status=status,
            detail=detail,
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle AppError exceptions."""
    problem = ProblemDetail(
        type=f"https://pathfinder.veupathdb.org/errors/{exc.code.value}",
        title=exc.title,
        status=exc.status,
        detail=exc.detail,
        instance=str(request.url),
        code=exc.code,
        errors=exc.errors,
    )
    return JSONResponse(
        status_code=exc.status,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPException."""
    code = ErrorCode.INTERNAL_ERROR
    if exc.status_code == 404:
        code = ErrorCode.NOT_FOUND
    elif exc.status_code == 401:
        code = ErrorCode.UNAUTHORIZED
    elif exc.status_code == 403:
        code = ErrorCode.FORBIDDEN
    elif exc.status_code == 429:
        code = ErrorCode.RATE_LIMITED

    problem = ProblemDetail(
        type=f"https://pathfinder.veupathdb.org/errors/{code.value}",
        title=str(exc.detail),
        status=exc.status_code,
        instance=str(request.url),
        code=code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )
