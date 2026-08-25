"""Who a veupathdb-wdk-mcp call acts as, and the WDK identity that credential grants."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from uuid import UUID

from assistant_core.platform.logging import get_logger
from mcp.server.auth.provider import AccessToken
from pydantic import ConfigDict, Field

from pathfinder.platform.config import get_settings
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.services.wdk_identity import resolve_veupathdb_bearer

logger = get_logger(__name__)


class CredentialMode(StrEnum):
    """The credential a call carries, in the admission record's vocabulary."""

    NONE = "none"
    SERVICE = "service"
    VEUPATHDB_USER = "veupathdb_user"


class McpCredential(AccessToken):
    """What a verified credential proves. ``user_id`` is set in user mode only."""

    model_config = ConfigDict(frozen=True)

    token: str = Field(repr=False)
    mode: CredentialMode
    user_id: UUID | None = None


def _refuse(mode: CredentialMode, reason: str) -> None:
    """Report a refused call by mode. The credential itself never reaches a log."""
    logger.info("Refused an MCP call", credential_mode=mode.value, reason=reason)


class VEuPathDBTokenVerifier:
    """Verifies an inbound bearer against the applications, then against VEuPathDB.

    The bearer resolves through the same OAuth signing key the application's own
    API uses, so one JWKS fetch and one cache serve both.
    """

    async def verify_token(self, token: str) -> McpCredential | None:
        """Verify a bearer. None refuses the call, and the transport answers 401."""
        presented = token.strip()
        if not presented:
            _refuse(CredentialMode.NONE, "the call carried no credential")
            return None

        application_id = get_settings().mcp_service_tokens.application_for(presented)
        if application_id is not None:
            return McpCredential(
                token=presented,
                client_id=application_id,
                scopes=[],
                mode=CredentialMode.SERVICE,
            )

        bearer = await resolve_veupathdb_bearer(presented)
        if bearer.user_id is None:
            _refuse(CredentialMode.VEUPATHDB_USER, bearer.rejection)
            return None
        return McpCredential(
            token=presented,
            client_id=str(bearer.user_id),
            scopes=[],
            mode=CredentialMode.VEUPATHDB_USER,
            user_id=bearer.user_id,
        )


@contextmanager
def wdk_identity(credential: McpCredential) -> Iterator[None]:
    """Act on WDK as the credential names.

    Only a user credential travels. A service credential leaves the request token
    empty, so the transport guard refuses a call under ``/users/``.
    """
    acts_as_user = credential.mode is CredentialMode.VEUPATHDB_USER
    reset = veupathdb_auth_token_ctx.set(credential.token if acts_as_user else None)
    try:
        yield
    finally:
        veupathdb_auth_token_ctx.reset(reset)
