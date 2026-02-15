Platform
========

Shared infrastructure: config, types, errors, security, and logging.
Used throughout the application. No business logic.

Overview
--------

- **Config** — Application settings (API keys, database URL, feature flags).
  Loaded from environment and .env files.
- **Types** — Shared type aliases: JSONObject, JSONArray, JSONValue.
- **Errors** — WDKError, ValidationError, ErrorCode. Consistent error handling.
- **Security** — Auth and authorization helpers.
- **Logging** — Structured logging setup.

Config
------

**Purpose:** Application settings. API keys (OpenAI, Anthropic, etc.), database
URL, Qdrant URL, feature flags (rag_enabled). Loaded via pydantic-settings.

**Key function:** :py:func:`get_settings`

.. automodule:: veupath_chatbot.platform.config
   :members:
   :undoc-members:
   :show-inheritance:

Types
-----

**Purpose:** Shared type aliases for untyped dict/list payloads. JSONObject,
JSONArray, JSONValue. Used throughout the codebase.

.. automodule:: veupath_chatbot.platform.types
   :members:
   :undoc-members:
   :show-inheritance:

Errors
------

**Purpose:** Error codes and exception types. WDKError for WDK API failures,
ValidationError for plan validation, ErrorCode enum. Used for consistent
HTTP error responses.

**Key classes:** :py:class:`WDKError`, :py:class:`ValidationError`

.. automodule:: veupath_chatbot.platform.errors
   :members:
   :undoc-members:
   :show-inheritance:

Security
--------

**Purpose:** Authentication and authorization. Token validation, permission
checks, user context. Used by HTTP deps and routers.

.. automodule:: veupath_chatbot.platform.security
   :members:
   :undoc-members:
   :show-inheritance:

Logging
-------

**Purpose:** Structured logging. get_logger returns a logger configured for
JSON/structlog output. Used by all modules.

**Key function:** :py:func:`get_logger`

.. automodule:: veupath_chatbot.platform.logging
   :members:
   :undoc-members:
   :show-inheritance:
