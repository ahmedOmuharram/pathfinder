"""What an inbound veupathdb-wdk-mcp credential proves, and the WDK identity it grants."""

from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from uuid import UUID, uuid4

import pytest
import structlog.testing

from pathfinder.mcp import auth
from pathfinder.mcp.auth import (
    CredentialMode,
    McpCredential,
    VEuPathDBTokenVerifier,
    wdk_identity,
)
from pathfinder.platform import security
from pathfinder.platform.config import get_settings
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.platform.errors import ExternalServiceError
from pathfinder.services.wdk_identity import VEuPathDBBearer

SERVICE_SECRET = "wdk-mcp-service-secret-0123456789ab"
USER_TOKEN = "a-registered-veupathdb-bearer-token"
GUEST_TOKEN = "a-guest-veupathdb-bearer-token"


@pytest.fixture
def mcp_credentials(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("PATHFINDER_MCP_SERVICE_TOKENS", f"gene-page:{SERVICE_SECRET}")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _stub_bearer(
    monkeypatch: pytest.MonkeyPatch, answer: VEuPathDBBearer | Exception
) -> None:
    async def resolve(token: str) -> VEuPathDBBearer:
        del token
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(auth, "resolve_veupathdb_bearer", resolve)


def test_the_bearer_resolver_is_the_one_the_api_uses() -> None:
    """The MCP server shares the api's JWKS path rather than fetching its own key."""
    assert auth.resolve_veupathdb_bearer is security.resolve_veupathdb_bearer


async def test_a_missing_credential_verifies_as_nothing(mcp_credentials: None) -> None:
    del mcp_credentials

    assert await VEuPathDBTokenVerifier().verify_token("") is None
    assert await VEuPathDBTokenVerifier().verify_token("   ") is None


async def test_the_service_secret_verifies_as_the_application(
    mcp_credentials: None,
) -> None:
    del mcp_credentials

    credential = await VEuPathDBTokenVerifier().verify_token(SERVICE_SECRET)

    assert credential is not None
    assert credential.mode is CredentialMode.SERVICE
    assert credential.client_id == "gene-page"
    assert credential.user_id is None


async def test_a_registered_bearer_verifies_as_the_user(
    mcp_credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del mcp_credentials
    user_id = uuid4()
    _stub_bearer(monkeypatch, VEuPathDBBearer(user_id=user_id))

    credential = await VEuPathDBTokenVerifier().verify_token(USER_TOKEN)

    assert credential is not None
    assert credential.mode is CredentialMode.VEUPATHDB_USER
    assert credential.user_id == user_id
    assert credential.client_id == str(user_id)
    assert credential.token == USER_TOKEN


async def test_a_guest_bearer_verifies_as_nothing(
    mcp_credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del mcp_credentials
    _stub_bearer(
        monkeypatch,
        VEuPathDBBearer(rejection="A guest VEuPathDB token cannot sign in"),
    )

    assert await VEuPathDBTokenVerifier().verify_token(GUEST_TOKEN) is None


async def test_an_unreadable_signing_key_is_not_a_refusal(
    mcp_credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A JWKS that cannot be read is 503 naming the provider, never a bad token."""
    del mcp_credentials
    _stub_bearer(
        monkeypatch,
        ExternalServiceError(
            service="VEuPathDB identity provider",
            detail="the identity provider cannot be read",
            status=HTTPStatus.SERVICE_UNAVAILABLE,
        ),
    )

    with pytest.raises(ExternalServiceError):
        await VEuPathDBTokenVerifier().verify_token(USER_TOKEN)


def test_the_user_mode_acts_on_wdk_as_the_user() -> None:
    credential = McpCredential(
        token=USER_TOKEN,
        client_id=str(UUID(int=1)),
        scopes=[],
        mode=CredentialMode.VEUPATHDB_USER,
        user_id=UUID(int=1),
    )

    with wdk_identity(credential):
        assert veupathdb_auth_token_ctx.get() == USER_TOKEN

    assert veupathdb_auth_token_ctx.get() is None


def test_the_service_mode_leaves_the_wdk_request_token_empty() -> None:
    """The transport guard refuses a call under /users/ without a request token."""
    credential = McpCredential(
        token=SERVICE_SECRET,
        client_id="gene-page",
        scopes=[],
        mode=CredentialMode.SERVICE,
    )

    with wdk_identity(credential):
        assert veupathdb_auth_token_ctx.get() is None


async def test_a_refusal_names_the_mode_and_never_the_credential(
    mcp_credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del mcp_credentials
    _stub_bearer(monkeypatch, VEuPathDBBearer(rejection="Invalid VEuPathDB token"))
    verifier = VEuPathDBTokenVerifier()

    with structlog.testing.capture_logs() as events:
        await verifier.verify_token("")
        await verifier.verify_token(USER_TOKEN)
        await verifier.verify_token(SERVICE_SECRET)

    modes = [event.get("credential_mode") for event in events]
    assert modes == [CredentialMode.NONE.value, CredentialMode.VEUPATHDB_USER.value]
    logged = repr(events)
    assert USER_TOKEN not in logged
    assert SERVICE_SECRET not in logged


def test_the_credential_never_prints_its_token() -> None:
    credential = McpCredential(
        token=USER_TOKEN,
        client_id="pathfinder",
        scopes=[],
        mode=CredentialMode.VEUPATHDB_USER,
    )

    assert USER_TOKEN not in repr(credential)
