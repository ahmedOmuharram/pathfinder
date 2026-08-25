"""What veupathdb-wdk-mcp publishes about itself, and how it refuses a call."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import httpx
import pytest
from mcp.shared.auth import ProtectedResourceMetadata
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from pathfinder.mcp import auth
from pathfinder.mcp.auth import CredentialMode, McpCredential
from pathfinder.mcp.metadata import (
    RESOURCE_NAME,
    guarded,
    protected_resource_routes,
)
from pathfinder.platform.config import get_settings
from pathfinder.services.wdk_identity import VEuPathDBBearer

BASE_URL = "https://wdk-mcp.veupathdb.org"
MCP_PATH = "/mcp"
METADATA_PATH = "/.well-known/oauth-protected-resource/mcp"
SERVICE_SECRET = "wdk-mcp-service-secret-0123456789ab"


@pytest.fixture
def mcp_deployment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("PATHFINDER_MCP_BASE_URL", BASE_URL)
    monkeypatch.setenv("PATHFINDER_MCP_SERVICE_TOKENS", f"gene-page:{SERVICE_SECRET}")
    monkeypatch.setenv("VEUPATHDB_OAUTH_URL", "https://auth.veupathdb.org")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _served_tool(scope: Scope, receive: Receive, send: Send) -> None:
    """Reports the mode of the credential the gate verified for this call."""
    credential: McpCredential = scope["user"].access_token
    await PlainTextResponse(f"served {credential.mode.value}")(scope, receive, send)


def _client() -> httpx.AsyncClient:
    app = Starlette(
        routes=[
            Route(MCP_PATH, endpoint=guarded(_served_tool), methods=["POST"]),
            *protected_resource_routes(),
        ]
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://wdk-mcp.test"
    )


async def test_the_metadata_document_carries_rfc_9728_required_fields(
    mcp_deployment: None,
) -> None:
    del mcp_deployment

    async with _client() as client:
        response = await client.get(METADATA_PATH)

    assert response.status_code == 200
    document = ProtectedResourceMetadata.model_validate_json(response.content)
    assert str(document.resource) == f"{BASE_URL}{MCP_PATH}"
    assert [str(server) for server in document.authorization_servers] == [
        "https://auth.veupathdb.org/"
    ]
    assert document.bearer_methods_supported == ["header"]
    assert document.resource_name == RESOURCE_NAME


async def test_the_authorization_server_is_configurable(
    mcp_deployment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del mcp_deployment
    monkeypatch.setenv("VEUPATHDB_OAUTH_URL", "https://auth.example.org")
    get_settings.cache_clear()

    async with _client() as client:
        response = await client.get(METADATA_PATH)

    document = ProtectedResourceMetadata.model_validate_json(response.content)
    assert [str(server) for server in document.authorization_servers] == [
        "https://auth.example.org/"
    ]


async def test_a_call_without_a_credential_is_refused_with_the_challenge(
    mcp_deployment: None,
) -> None:
    del mcp_deployment

    async with _client() as client:
        response = await client.post(MCP_PATH, json={})

    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert challenge.startswith("Bearer ")
    assert f'resource_metadata="{BASE_URL}{METADATA_PATH}"' in challenge


async def test_a_rejected_credential_is_refused_with_the_challenge(
    mcp_deployment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del mcp_deployment

    async def rejected(token: str) -> VEuPathDBBearer:
        del token
        return VEuPathDBBearer(rejection="Invalid VEuPathDB token")

    monkeypatch.setattr(auth, "resolve_veupathdb_bearer", rejected)

    async with _client() as client:
        response = await client.post(
            MCP_PATH, json={}, headers={"Authorization": "Bearer not-a-real-token"}
        )

    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert f'resource_metadata="{BASE_URL}{METADATA_PATH}"' in challenge
    assert "not-a-real-token" not in response.text
    assert "not-a-real-token" not in challenge


async def test_a_service_credential_reaches_the_call_as_the_application(
    mcp_deployment: None,
) -> None:
    del mcp_deployment

    async with _client() as client:
        response = await client.post(
            MCP_PATH, json={}, headers={"Authorization": f"Bearer {SERVICE_SECRET}"}
        )

    assert response.status_code == 200
    assert response.text == f"served {CredentialMode.SERVICE.value}"


async def test_a_registered_bearer_reaches_the_call_as_the_user(
    mcp_deployment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del mcp_deployment

    async def registered(token: str) -> VEuPathDBBearer:
        del token
        return VEuPathDBBearer(user_id=uuid4())

    monkeypatch.setattr(auth, "resolve_veupathdb_bearer", registered)

    async with _client() as client:
        response = await client.post(
            MCP_PATH, json={}, headers={"Authorization": "Bearer a-registered-token"}
        )

    assert response.status_code == 200
    assert response.text == f"served {CredentialMode.VEUPATHDB_USER.value}"


async def test_the_document_is_unreachable_without_a_public_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATHFINDER_MCP_BASE_URL", "")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="PATHFINDER_MCP_BASE_URL"):
        protected_resource_routes()

    get_settings.cache_clear()
