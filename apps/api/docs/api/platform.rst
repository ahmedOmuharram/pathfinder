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

Design Decisions
~~~~~~~~~~~~~~~~

.. dropdown:: Redis for event bus
   :icon: broadcast

   The platform event bus uses Redis Streams for durable
   event delivery. Chat streams and experiment executions publish events that
   clients consume via SSE. Redis Streams support consumer groups, cursor-based
   replay, and TTL-based cleanup — all necessary for reliable long-running
   operations that may outlive HTTP connections.

.. dropdown:: Pydantic settings
   :icon: gear

   Configuration uses ``pydantic-settings`` with TOML +
   environment variable layering. TOML provides checked-in defaults; environment
   variables override for deployment. This avoids the "which .env file?" problem
   while keeping sensitive values out of version control.

.. dropdown:: Structured logging via structlog
   :icon: log

   All logging uses ``structlog`` with JSON
   output. This enables structured queries in log aggregation tools (filtering by
   ``user_id``, ``strategy_id``, ``tool_name``) without string parsing. Development
   mode uses human-readable console output.

.. dropdown:: Context variables for request state
   :icon: link

   Request-scoped state (auth token, user
   ID, site context) propagates via Python ``contextvars``. This avoids threading
   state through every function signature while remaining async-safe (each task
   gets its own context copy).

.. tip::

   All configuration values can be overridden via environment variables.
   See ``config.toml`` for defaults and ``platform/config.py`` for the
   full settings schema.

Config
------

**Purpose:** Application settings. API keys (OpenAI, Anthropic, etc.), database
URL, and feature flags. Loaded via pydantic-settings.

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

Context
-------

**Purpose:** Context variables for request-scoped state. Auth tokens,
user IDs, and other per-request data propagated via contextvars.

.. automodule:: veupath_chatbot.platform.context
   :members:
   :undoc-members:
   :show-inheritance:

Events
------

**Purpose:** Application event bus for cross-cutting concerns and
inter-service communication.

.. automodule:: veupath_chatbot.platform.events
   :members:
   :undoc-members:
   :show-inheritance:

Health
------

**Purpose:** Health check logic and readiness probe implementation.

.. automodule:: veupath_chatbot.platform.health
   :members:
   :undoc-members:
   :show-inheritance:

Redis
-----

**Purpose:** Redis client management, connection pooling, and utilities.

.. automodule:: veupath_chatbot.platform.redis
   :members:
   :undoc-members:
   :show-inheritance:

Store
-----

**Purpose:** Generic store abstractions for in-memory + persistence patterns.

.. automodule:: veupath_chatbot.platform.store
   :members:
   :undoc-members:
   :show-inheritance:

Tasks
-----

**Purpose:** Background task infrastructure and management.

.. automodule:: veupath_chatbot.platform.tasks
   :members:
   :undoc-members:
   :show-inheritance:

Tool Errors
-----------

**Purpose:** Tool-specific error formatting and handling utilities.

.. automodule:: veupath_chatbot.platform.tool_errors
   :members:
   :undoc-members:
   :show-inheritance:

Parsing
-------

**Purpose:** Input parsing utilities for request processing.

.. automodule:: veupath_chatbot.platform.parsing
   :members:
   :undoc-members:
   :show-inheritance:

Pydantic Validation
-------------------

**Purpose:** Pydantic validation helpers and custom validators.

.. automodule:: veupath_chatbot.platform.pydantic_validation
   :members:
   :undoc-members:
   :show-inheritance:
