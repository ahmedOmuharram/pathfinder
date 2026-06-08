import json

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from limits import parse
from slowapi.errors import RateLimitExceeded
from slowapi.wrappers import Limit
from starlette.requests import Request

from pathfinder.platform.error_handlers import (
    app_error_handler,
    http_exception_handler,
    rate_limit_handler,
    request_validation_handler,
)
from pathfinder.platform.errors import AppError, ErrorCode

_PROBLEM_JSON = "application/problem+json"


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("test", 80),
            "path": "/api/v1/x",
            "query_string": b"",
            "headers": [],
        }
    )


def _body(resp: JSONResponse) -> dict[str, object]:
    return json.loads(bytes(resp.body))


async def test_app_error_handler_returns_problem_json() -> None:
    resp = await app_error_handler(
        _request(),
        AppError(code=ErrorCode.WDK_ERROR, title="WDK", status=502, detail="upstream"),
    )
    assert resp.media_type == _PROBLEM_JSON
    assert resp.status_code == 502
    body = _body(resp)
    assert body["status"] == 502
    assert body["code"] == "WDK_ERROR"
    assert body["detail"] == "upstream"


async def test_http_exception_handler_returns_problem_json() -> None:
    resp = await http_exception_handler(
        _request(), HTTPException(status_code=404, detail="missing")
    )
    assert resp.media_type == _PROBLEM_JSON
    assert resp.status_code == 404
    assert _body(resp)["code"] == "NOT_FOUND"


async def test_request_validation_handler_returns_problem_json() -> None:
    exc = RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("query", "x"),
                "msg": "Field required",
                "input": None,
            }
        ]
    )
    resp = await request_validation_handler(_request(), exc)
    assert resp.media_type == _PROBLEM_JSON
    assert resp.status_code == 422
    body = _body(resp)
    assert body["code"] == "VALIDATION_ERROR"
    errors = body["errors"]
    assert isinstance(errors, list)
    assert errors[0]["msg"] == "Field required"


async def test_rate_limit_handler_returns_problem_json() -> None:
    limit = Limit(
        parse("5/minute"), lambda: "k", "5/minute", False, None, None, None, 1, False
    )
    resp = await rate_limit_handler(_request(), RateLimitExceeded(limit))
    assert resp.media_type == _PROBLEM_JSON
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "60"
    assert _body(resp)["code"] == "RATE_LIMITED"
