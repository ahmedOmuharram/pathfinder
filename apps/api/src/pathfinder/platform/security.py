"""Authentication, authorization, rate limiting, CSRF, and request guards."""

import json
import time
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import APIKeyCookie
from jwt.types import Options
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from pathfinder.platform.config import get_settings
from pathfinder.platform.context import user_id_ctx
from pathfinder.platform.error_handlers import problem_response
from pathfinder.platform.errors import ErrorCode, UnauthorizedError

_JWT_ALGORITHM = "HS256"
_JWT_DECODE_OPTIONS: Options = {"require": ["exp", "sub"]}

# Cookie auth is the public contract, so OpenAPI documents only the cookie.
# An Authorization header is also accepted, for local tools.
auth_cookie = APIKeyCookie(name="pathfinder-auth", auto_error=False)

limiter = Limiter(key_func=get_remote_address)


def _extract_token(cookie_token: str | None, request: Request) -> str | None:
    """Extract the raw JWT string from a cookie or Authorization header."""
    raw = str(cookie_token) if cookie_token else None

    if not raw:
        raw = request.headers.get("Authorization")

    if not raw:
        return None

    scheme, _, token = raw.partition(" ")
    if scheme.lower() == "bearer":
        return token or None
    return raw


async def get_optional_user(
    request: Request,
    cookie_token: Annotated[str | None, Depends(auth_cookie)] = None,
) -> UUID | None:
    """Return the current user ID, or None when the request is not authenticated."""
    token = _extract_token(cookie_token, request)
    if not token:
        return None

    try:
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.api_secret_key,
            algorithms=[_JWT_ALGORITHM],
            options=_JWT_DECODE_OPTIONS,
        )
        user_id = UUID(payload["sub"])
        user_id_ctx.set(user_id)
    except jwt.InvalidTokenError, ValueError, KeyError:
        return None
    else:
        return user_id


async def get_current_user(
    user_id: Annotated[UUID | None, Depends(get_optional_user)],
) -> UUID:
    """Return the current user ID. Raise UnauthorizedError when there is none."""
    if user_id is None:
        raise UnauthorizedError(detail="Not authenticated")
    return user_id


def create_user_token(user_id: UUID, expires_in: int = 86400) -> str:
    """Create a signed JWT for a user.

    :param expires_in: Token lifetime in seconds.
    """
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "exp": int(time.time()) + expires_in,
    }
    return jwt.encode(payload, settings.api_secret_key, algorithm=_JWT_ALGORITHM)


_CSRF_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def csrf_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Require the X-Requested-With header on state-changing requests.

    A browser cannot send a custom header cross-origin without a CORS
    preflight, so a forged form or navigation cannot set it.
    """
    if (
        request.method not in _CSRF_SAFE_METHODS
        and not request.headers.get("X-Requested-With", "").strip()
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": "Missing required X-Requested-With header"},
        )
    return await call_next(request)


class RejectNullBytesMiddleware:
    """Reject a NUL character in the URL or a JSON body before the route runs.

    PostgreSQL text cannot hold NUL. The check must precede the route, because
    a body value reaches the database at commit time, after the response, where
    exception handlers no longer apply. Pure ASGI, so the body can be read and
    replayed to the app.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if "\x00" in request.url.path or any(
            "\x00" in key or "\x00" in value
            for key, value in request.query_params.multi_items()
        ):
            await self._reject(request, "URL", scope, receive, send)
            return

        if not _is_json_request(request):
            await self.app(scope, receive, send)
            return

        body, messages = await _drain_body(receive)
        if _body_carries_null(body):
            await self._reject(request, "Request body", scope, receive, send)
            return

        await self.app(scope, _replay(messages, receive), send)

    async def _reject(
        self,
        request: Request,
        source: str,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        response = problem_response(
            request,
            status=HTTPStatus.UNPROCESSABLE_ENTITY,
            code=ErrorCode.VALIDATION_ERROR,
            title="Request validation failed",
            detail=f"{source} must not contain null characters",
        )
        await response(scope, receive, send)


def _is_json_request(request: Request) -> bool:
    return "json" in request.headers.get("content-type", "")


def _body_carries_null(body: bytes) -> bool:
    """Report whether a JSON body decodes to a string that contains NUL.

    A NUL arrives as an escape sequence, and those same bytes can also spell an
    escaped backslash, so the byte scan is only a prefilter. The parsed value
    decides.
    """
    if b"\x00" not in body and b"\\u0000" not in body:
        return False
    try:
        parsed = json.loads(body)
    except ValueError:
        # The route owns the error for malformed JSON.
        return False
    return _contains_null(parsed)


def _contains_null(value: object) -> bool:
    if isinstance(value, str):
        return "\x00" in value
    if isinstance(value, dict):
        return any(
            _contains_null(key) or _contains_null(item) for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_null(item) for item in value)
    return False


async def _drain_body(receive: Receive) -> tuple[bytes, list[Message]]:
    """Read the request body to completion, and keep every message for replay."""
    body = bytearray()
    messages: list[Message] = []
    more_body = True
    while more_body:
        message = await receive()
        messages.append(message)
        if message["type"] != "http.request":
            break
        body.extend(message.get("body", b""))
        more_body = bool(message.get("more_body", False))
    return bytes(body), messages


def _replay(messages: list[Message], receive: Receive) -> Receive:
    """Return a receive callable that replays drained messages, then the real stream."""
    pending = iter(messages)

    async def replayed() -> Message:
        return next(pending, None) or await receive()

    return replayed
