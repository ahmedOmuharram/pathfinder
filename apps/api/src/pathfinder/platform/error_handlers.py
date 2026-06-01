"""FastAPI exception handlers that render errors as problem+json."""

from http import HTTPStatus

import structlog
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from pathfinder.platform.errors import AppError, ErrorCode, ProblemDetail

_logger = structlog.get_logger(__name__)

_STATUS_TO_ERROR_CODE: dict[int, ErrorCode] = {
    HTTPStatus.NOT_FOUND: ErrorCode.NOT_FOUND,
    HTTPStatus.UNAUTHORIZED: ErrorCode.UNAUTHORIZED,
    HTTPStatus.FORBIDDEN: ErrorCode.FORBIDDEN,
    HTTPStatus.TOO_MANY_REQUESTS: ErrorCode.RATE_LIMITED,
}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle AppError exceptions."""
    log = _logger.bind(
        method=request.method,
        path=request.url.path,
        status=exc.status,
        code=exc.code.value,
        title=exc.title,
        detail=exc.detail,
        errors=exc.errors,
    )
    if exc.status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        log.error("Request failed", exc_info=exc)
    else:
        log.warning("Request failed")
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
