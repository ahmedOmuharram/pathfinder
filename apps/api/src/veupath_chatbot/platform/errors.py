"""Typed error model with problem+json responses."""

from enum import StrEnum
from http import HTTPStatus

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from veupath_chatbot.platform.types import JSONArray

_STATUS_TO_ERROR_CODE: dict[int, "ErrorCode"] = {}


def _init_status_map() -> None:
    """Populate _STATUS_TO_ERROR_CODE after ErrorCode is defined."""
    _STATUS_TO_ERROR_CODE[HTTPStatus.NOT_FOUND] = ErrorCode.NOT_FOUND
    _STATUS_TO_ERROR_CODE[HTTPStatus.UNAUTHORIZED] = ErrorCode.UNAUTHORIZED
    _STATUS_TO_ERROR_CODE[HTTPStatus.FORBIDDEN] = ErrorCode.FORBIDDEN
    _STATUS_TO_ERROR_CODE[HTTPStatus.TOO_MANY_REQUESTS] = ErrorCode.RATE_LIMITED


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


_init_status_map()


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
    """Strategy compilation or build failure.

    Raised when strategy compilation, step creation, or step-tree
    assembly fails — distinguishes build-pipeline errors from generic
    ValueError/TypeError so callers and log filters can react specifically.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(
            code=ErrorCode.STRATEGY_COMPILATION_ERROR,
            title="Strategy compilation failed",
            status=500,
            detail=detail,
        )


class ExternalServiceError(AppError):
    """Non-WDK external service failure.

    Raised when an external HTTP service (CrossRef, PubMed, EuropePMC,
    OpenAlex, etc.) is unreachable or returns an unexpected response.
    Distinguishes "PubMed is down" from "our parsing code has a bug".
    """

    def __init__(self, service: str, detail: str, status: int = 502) -> None:
        super().__init__(
            code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            title=f"External service error: {service}",
            status=status,
            detail=detail,
        )


class DataParsingError(AppError):
    """Unexpected data shape from an API response.

    Raised when an external API (WDK, site-search, research services)
    returns data that cannot be parsed into the expected structure.
    Distinguishes "API returned garbage" from "our logic has a bug".
    """

    def __init__(self, detail: str) -> None:
        super().__init__(
            code=ErrorCode.DATA_PARSING_ERROR,
            title="Data parsing failed",
            status=500,
            detail=detail,
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle AppError exceptions."""
    problem = ProblemDetail(
        type=f"/errors/{exc.code.value}",
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
    code = _STATUS_TO_ERROR_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

    problem = ProblemDetail(
        type=f"/errors/{code.value}",
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
