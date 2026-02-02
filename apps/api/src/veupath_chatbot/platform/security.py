"""Authentication, authorization, and rate limiting."""

import hashlib
import hmac
import secrets
import time
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyCookie
from fastapi.security.api_key import APIKey
from pydantic import BaseModel

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.context import user_id_ctx

# Cookie-based auth is the public contract. We still accept an Authorization header
# as a non-documented fallback (parsed from request.headers) to avoid breaking
# internal tooling, but OpenAPI should reflect cookies.
auth_cookie = APIKeyCookie(name="pathfinder-auth", auto_error=False)


class TokenPayload(BaseModel):
    """JWT-like token payload (simplified for demo)."""

    user_id: UUID
    exp: int


def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return secrets.token_urlsafe(32)


def verify_csrf_token(token: str, session_token: str) -> bool:
    """Verify CSRF token against session."""
    settings = get_settings()
    expected = hmac.new(
        settings.api_secret_key.encode(),
        session_token.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(token, expected)


async def get_optional_user(
    request: Request,
    cookie_token: Annotated[APIKey | None, Depends(auth_cookie)] = None,
) -> UUID | None:
    """Get current user ID if authenticated (optional)."""
    token_header: str | None = str(cookie_token) if cookie_token else None

    # Undocumented fallback: allow Authorization header for local tools.
    if not token_header:
        token_header = request.headers.get("Authorization")

    if not token_header:
        return None

    try:
        # Simple token validation (replace with proper JWT in production)
        scheme, _, token = token_header.partition(" ")
        if scheme.lower() == "bearer":
            if not token:
                return None
        else:
            token = token_header

        # For demo: decode simple token format "user_id:expiry:signature"
        parts = token.split(":")
        if len(parts) != 3:
            return None

        user_id = UUID(parts[0])
        expiry = int(parts[1])

        if expiry < int(time.time()):
            return None

        # Verify signature
        settings = get_settings()
        expected_sig = hmac.new(
            settings.api_secret_key.encode(),
            f"{user_id}:{expiry}".encode(),
            hashlib.sha256,
        ).hexdigest()[:16]

        if not hmac.compare_digest(parts[2], expected_sig):
            return None

        # Set context
        user_id_ctx.set(user_id)
        return user_id

    except (ValueError, IndexError):
        return None


async def get_current_user(
    user_id: Annotated[UUID | None, Depends(get_optional_user)],
) -> UUID:
    """Get current user ID (required)."""
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def create_user_token(user_id: UUID, expires_in: int = 86400) -> str:
    """Create a simple user token (for demo purposes)."""
    settings = get_settings()
    expiry = int(time.time()) + expires_in
    signature = hmac.new(
        settings.api_secret_key.encode(),
        f"{user_id}:{expiry}".encode(),
        hashlib.sha256,
    ).hexdigest()[:16]
    return f"{user_id}:{expiry}:{signature}"


class RateLimiter:
    """Simple in-memory rate limiter (use Redis in production)."""

    def __init__(self, requests_per_minute: int = 60) -> None:
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[float]] = {}

    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed."""
        now = time.time()
        minute_ago = now - 60

        # Clean old requests
        if key in self.requests:
            self.requests[key] = [t for t in self.requests[key] if t > minute_ago]
        else:
            self.requests[key] = []

        # Check limit
        if len(self.requests[key]) >= self.requests_per_minute:
            return False

        self.requests[key].append(now)
        return True


# Global rate limiter instance
rate_limiter = RateLimiter()


async def check_rate_limit(request: Request) -> None:
    """Check rate limit for request."""
    # Use IP address as key (in production, consider user ID too)
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

