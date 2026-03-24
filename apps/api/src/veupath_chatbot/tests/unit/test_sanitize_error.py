"""Unit tests for sanitize_error_for_client — error sanitization for SSE events.

Verifies that:
- AppError subclasses preserve their user-facing messages
- Non-AppError exceptions return a generic message (no information leakage)
"""

from veupath_chatbot.platform.errors import (
    AppError,
    DataParsingError,
    ErrorCode,
    ExternalServiceError,
    InternalError,
    NotFoundError,
    StrategyCompilationError,
    ValidationError,
    WDKError,
    sanitize_error_for_client,
)


class TestSanitizeAppErrors:
    """AppError subclasses carry intentionally user-safe messages."""

    def test_wdk_error_preserves_message(self):
        exc = WDKError("search returned invalid response")
        result = sanitize_error_for_client(exc)
        assert "VEuPathDB service error" in result
        assert "search returned invalid response" in result

    def test_not_found_error_preserves_message(self):
        exc = NotFoundError(detail="Strategy 42 not found")
        result = sanitize_error_for_client(exc)
        assert "not found" in result.lower()

    def test_validation_error_preserves_message(self):
        exc = ValidationError(detail="field 'name' is required")
        result = sanitize_error_for_client(exc)
        assert "Validation failed" in result

    def test_internal_error_preserves_title(self):
        exc = InternalError(title="Unexpected failure")
        result = sanitize_error_for_client(exc)
        assert "Unexpected failure" in result

    def test_strategy_compilation_error(self):
        exc = StrategyCompilationError("step tree is cyclic")
        result = sanitize_error_for_client(exc)
        assert "compilation" in result.lower()

    def test_external_service_error(self):
        exc = ExternalServiceError("PubMed", "connection timeout")
        result = sanitize_error_for_client(exc)
        assert "PubMed" in result

    def test_data_parsing_error(self):
        exc = DataParsingError("missing 'results' key")
        result = sanitize_error_for_client(exc)
        assert "parsing" in result.lower()

    def test_base_app_error(self):
        exc = AppError(
            code=ErrorCode.INTERNAL_ERROR,
            title="Custom error",
            detail="some detail",
        )
        result = sanitize_error_for_client(exc)
        assert "Custom error" in result
        assert "some detail" in result


class TestSanitizeNonAppErrors:
    """Non-AppError exceptions must return a generic message to prevent leakage."""

    def test_runtime_error_is_sanitized(self):
        exc = RuntimeError("SELECT * FROM users WHERE id=1; -- SQL injection detail")
        result = sanitize_error_for_client(exc)
        assert result == "An internal error occurred"
        assert "SELECT" not in result

    def test_value_error_is_sanitized(self):
        exc = ValueError("/var/www/private/config.yaml not found")
        result = sanitize_error_for_client(exc)
        assert result == "An internal error occurred"
        assert "/var/www" not in result

    def test_os_error_is_sanitized(self):
        exc = OSError("[Errno 13] Permission denied: '/etc/shadow'")
        result = sanitize_error_for_client(exc)
        assert result == "An internal error occurred"
        assert "/etc/shadow" not in result

    def test_key_error_is_sanitized(self):
        exc = KeyError("internal_api_key")
        result = sanitize_error_for_client(exc)
        assert result == "An internal error occurred"

    def test_type_error_is_sanitized(self):
        exc = TypeError("NoneType has no attribute 'query'")
        result = sanitize_error_for_client(exc)
        assert result == "An internal error occurred"

    def test_connection_error_is_sanitized(self):
        exc = ConnectionError("http://internal-redis:6379 refused")
        result = sanitize_error_for_client(exc)
        assert result == "An internal error occurred"
        assert "redis" not in result

    def test_generic_exception_is_sanitized(self):
        exc = Exception("stack trace with internal paths")
        result = sanitize_error_for_client(exc)
        assert result == "An internal error occurred"

    def test_timeout_error_is_sanitized(self):
        exc = TimeoutError("asyncio.wait_for timed out after 30s")
        result = sanitize_error_for_client(exc)
        assert result == "An internal error occurred"
