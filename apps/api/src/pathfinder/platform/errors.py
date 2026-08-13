"""Typed error model with problem+json responses."""

from enum import StrEnum

import pydantic
from pydantic import BaseModel

from pathfinder.platform.types import JSONArray


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
    ENSURE_SINGLE_OUTPUT_FAILED = "ENSURE_SINGLE_OUTPUT_FAILED"

    # Compilation / data processing
    STRATEGY_COMPILATION_ERROR = "STRATEGY_COMPILATION_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    DATA_PARSING_ERROR = "DATA_PARSING_ERROR"

    # Conversation
    CONVERSATION_NOT_FOUND = "CONVERSATION_NOT_FOUND"

    # Specialists / launchers
    SPECIALIST_PRECONDITION_FAILED = "SPECIALIST_PRECONDITION_FAILED"
    SESSION_CONFLICT = "SESSION_CONFLICT"


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
        msg = f"{title}: {detail}" if detail else title
        super().__init__(msg)


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


class StrategyCompilationError(AppError):
    """Strategy compilation, step creation, or step-tree assembly failure."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            code=ErrorCode.STRATEGY_COMPILATION_ERROR,
            title="Strategy compilation failed",
            status=500,
            detail=detail,
        )


class ExternalServiceError(AppError):
    """A non-WDK external service is unreachable or answers unexpectedly."""

    def __init__(self, service: str, detail: str, status: int = 502) -> None:
        super().__init__(
            code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            title=f"External service error: {service}",
            status=status,
            detail=detail,
        )


class DataParsingError(AppError):
    """An external API returned data that does not match the expected shape."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            code=ErrorCode.DATA_PARSING_ERROR,
            title="Data parsing failed",
            status=500,
            detail=detail,
        )


def validate_response[M: BaseModel](model: type[M], raw: object, context: str) -> M:
    """Validate an external API response and raise ``DataParsingError``."""
    try:
        return model.model_validate(raw)
    except pydantic.ValidationError as e:
        msg = f"Unexpected {context}: {e}"
        raise DataParsingError(msg) from e


_GENERIC_ERROR = "An internal error occurred"


def sanitize_error_for_client(exc: BaseException) -> str:
    """Return a user-safe error message.

    Only an ``AppError`` carries a user-facing title and detail. Every other
    exception gets a generic message.
    """
    if isinstance(exc, AppError):
        return str(exc)
    return _GENERIC_ERROR
