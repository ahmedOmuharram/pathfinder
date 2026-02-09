import json

import pytest
from starlette.requests import Request

from veupath_chatbot.platform.errors import InternalError, app_error_handler


@pytest.mark.anyio
async def test_internal_error_is_problem_detail() -> None:
    req = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/boom",
            "raw_path": b"/boom",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
            "client": ("127.0.0.1", 12345),
        }
    )
    resp = await app_error_handler(req, InternalError(title="Boom", detail="Details"))
    assert resp.status_code == 500
    assert resp.media_type == "application/problem+json"
    body = json.loads(bytes(resp.body).decode("utf-8"))
    assert body["code"] == "INTERNAL_ERROR"
    assert body["title"] == "Boom"
    assert body["detail"] == "Details"
    assert body["status"] == 500
