"""Tests for Langfuse SDK client singleton."""

from unittest.mock import MagicMock, patch

import pathfinder.platform.langfuse.client as client_module
from pathfinder.platform.langfuse.client import get_langfuse


def test_get_langfuse_returns_none_when_not_configured() -> None:
    """Returns None when LANGFUSE_SECRET_KEY is empty."""
    client_module._client = None
    client_module._initialized = False

    mock_settings = MagicMock(
        langfuse_secret_key="", langfuse_public_key="", langfuse_host=""
    )
    with patch.object(client_module, "get_settings", return_value=mock_settings):
        result = get_langfuse()

    assert result is None
    assert client_module._initialized is True

    # Reset
    client_module._client = None
    client_module._initialized = False


def test_get_langfuse_returns_cached_none() -> None:
    """Second call returns cached None without re-checking settings."""
    client_module._client = None
    client_module._initialized = True

    result = get_langfuse()
    assert result is None

    # Reset
    client_module._initialized = False
