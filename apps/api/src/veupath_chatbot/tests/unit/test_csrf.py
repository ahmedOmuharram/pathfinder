"""Unit tests for CSRF middleware (X-Requested-With header check)."""

import pytest
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from veupath_chatbot.platform.security import csrf_middleware


def _make_request(
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> StarletteRequest:
    raw_headers = [
        (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
    ]
    return StarletteRequest(
        {
            "type": "http",
            "method": method,
            "path": "/api/v1/test",
            "query_string": b"",
            "headers": raw_headers,
        }
    )


async def _passthrough(request: StarletteRequest) -> Response:
    return Response(status_code=200)


class TestCsrfMiddleware:
    """X-Requested-With header is required on state-changing HTTP methods."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
    async def test_safe_methods_pass_without_header(self, method: str):
        request = _make_request(method=method)
        response = await csrf_middleware(request, _passthrough)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    async def test_blocked_without_header(self, method: str):
        request = _make_request(method=method)
        response = await csrf_middleware(request, _passthrough)
        assert response.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    async def test_passes_with_header(self, method: str):
        request = _make_request(
            method=method,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        response = await csrf_middleware(request, _passthrough)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_any_nonempty_header_value_accepted(self):
        request = _make_request(
            method="POST",
            headers={"X-Requested-With": "fetch"},
        )
        response = await csrf_middleware(request, _passthrough)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_header_value_rejected(self):
        request = _make_request(
            method="POST",
            headers={"X-Requested-With": ""},
        )
        response = await csrf_middleware(request, _passthrough)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_403_body_describes_error(self):
        request = _make_request(method="POST")
        response = await csrf_middleware(request, _passthrough)
        assert response.status_code == 403
        body = response.body.decode()
        assert "X-Requested-With" in body
