"""Unit tests for platform.config — Settings validation and edge cases.

Focuses on:
- Production secret key validation
- Default values safety
- TOML config source behavior
- Computed fields
- Type coercion for settings
"""

import os
import re
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from veupath_chatbot.platform.config import Settings

_TEST_SECRET = "test-key-that-is-at-least-32-chars-long"


class TestSettingsDefaults:
    """Verify default values are reasonable."""

    def test_default_env_is_development(self):
        with patch.dict(os.environ, {}, clear=False):
            s = Settings(
                _env_file=None,
                api_secret_key=_TEST_SECRET,
            )
            assert s.api_env == "development"

    def test_is_development_computed(self):
        s = Settings(
            _env_file=None,
            api_env="development",
            api_secret_key=_TEST_SECRET,
        )
        assert s.is_development is True
        assert s.is_production is False

    def test_is_production_computed(self):
        s = Settings(
            _env_file=None,
            api_env="production",
            api_secret_key="production-secret-key-that-is-long-enough-here",
        )
        assert s.is_production is True
        assert s.is_development is False

    def test_default_cors_origins(self):
        s = Settings(
            _env_file=None,
            api_secret_key=_TEST_SECRET,
        )
        assert "http://localhost:3000" in s.cors_origins


class TestProductionValidation:
    """Production environment should reject dev-only settings."""

    def test_production_rejects_placeholder_secret_key(self):
        """Production mode with placeholder secret keys should raise."""
        with pytest.raises(ValueError, match="API_SECRET_KEY must be set"):
            Settings(
                _env_file=None,
                api_env="production",
                api_secret_key="change-me-32-chars-min-xxxx-xxxx",
            )

    def test_production_accepts_real_secret_key(self):
        s = Settings(
            _env_file=None,
            api_env="production",
            api_secret_key="a-real-production-secret-key-that-is-long-enough",
        )
        assert s.is_production is True

    def test_staging_rejects_placeholder_secret_key(self):
        """Staging mode must also reject placeholder secret keys."""
        with pytest.raises(ValueError, match="API_SECRET_KEY must be set"):
            Settings(
                _env_file=None,
                api_env="staging",
                api_secret_key="dev-only-secret-key-change-in-prod",
            )

    def test_staging_accepts_real_secret_key(self):
        s = Settings(
            _env_file=None,
            api_env="staging",
            api_secret_key="a-real-staging-secret-key-that-is-long-enough",
        )
        assert s.api_env == "staging"


class TestSecretKeyValidation:
    """Secret key must be at least 32 characters."""

    def test_short_secret_key_rejected(self):
        """Keys shorter than 32 chars should fail pydantic validation."""
        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                api_secret_key="too-short",
            )

    def test_exactly_32_char_key_accepted(self):
        s = Settings(
            _env_file=None,
            api_secret_key="a" * 32,
        )
        assert len(s.api_secret_key) == 32


class TestEnvironmentLiteral:
    """api_env should only accept valid literal values."""

    def test_invalid_env_rejected(self):
        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                api_env="invalid_environment",
                api_secret_key=_TEST_SECRET,
            )

    def test_all_valid_envs(self):
        for env in ("development", "staging", "production"):
            key = (
                "test-key-that-is-at-least-32-chars-long"
                if env == "development"
                else "a-real-production-secret-key-that-is-long-enough"
            )
            s = Settings(_env_file=None, api_env=env, api_secret_key=key)
            assert s.api_env == env


class TestCorsOriginRegex:
    """CORS origin regex safety checks."""

    def test_default_regex_matches_localhost(self):
        s = Settings(
            _env_file=None,
            api_secret_key=_TEST_SECRET,
        )
        regex = s.cors_origin_regex
        assert regex is not None
        assert re.match(regex, "http://localhost:3000")
        assert re.match(regex, "http://127.0.0.1:8080")
        assert re.match(regex, "https://localhost")

    def test_default_regex_rejects_external(self):
        s = Settings(
            _env_file=None,
            api_secret_key=_TEST_SECRET,
        )
        regex = s.cors_origin_regex
        assert regex is not None
        assert not re.match(regex, "http://evil.com")
        assert not re.match(regex, "http://localhost.evil.com")

    def test_cors_regex_allows_no_port(self):
        """Regex should match localhost without a port."""
        s = Settings(
            _env_file=None,
            api_secret_key=_TEST_SECRET,
        )
        regex = s.cors_origin_regex
        assert regex is not None
        assert re.match(regex, "http://localhost")
        assert re.match(regex, "https://localhost")
