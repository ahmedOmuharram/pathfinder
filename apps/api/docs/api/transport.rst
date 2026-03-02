HTTP Transport
==============

FastAPI dependencies, SSE streaming, and HTTP-layer utilities. Connects
the HTTP API to the chat and strategy services.

Overview
--------

- **Dependencies** — Request-scoped deps: auth, DB session, strategy loading.
  Injected into router handlers.
- **Streaming** — SSE (Server-Sent Events) for chat. Event formatting,
  chunk encoding, stream lifecycle.

Dependencies
------------

**Purpose:** FastAPI dependencies. Provide auth context, DB session, strategy
loading, site context. Used by chat and strategies routers.

**Key functions:** :py:func:`get_db_session`, :py:func:`get_current_user`,
:py:func:`get_site_context` (or equivalent)

.. automodule:: veupath_chatbot.transport.http.deps
   :members:
   :undoc-members:
   :show-inheritance:

Streaming
---------

**Purpose:** SSE streaming for chat. Format events (message_start, tool_call_start,
etc.), encode as SSE chunks, manage stream lifecycle. Used by the chat endpoint.

**Key functions:** Event formatting, SSE response building

.. automodule:: veupath_chatbot.transport.http.streaming
   :members:
   :undoc-members:
   :show-inheritance:

SSE Helpers
-----------

**Purpose:** SSE event formatting utilities. Encode events as SSE-formatted
strings with proper ``data:`` prefixes and newline terminators.

.. automodule:: veupath_chatbot.transport.http.sse
   :members:
   :undoc-members:
   :show-inheritance:

Routers
-------

FastAPI routers that define the HTTP API surface. Each router handles a
specific domain area.

.. automodule:: veupath_chatbot.transport.http.routers.chat
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.sites
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.steps
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.models
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.health
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.control_sets
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.veupathdb_auth
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.strategies.crud
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.strategies.plan
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.strategies.counts
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.strategies.wdk_import
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.experiments.crud
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.experiments.execution
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.experiments.evaluation
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.experiments.analysis
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.experiments.cross_validation
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.experiments.enrichment
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.experiments.comparison
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.experiments.ai_assist
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.experiments.results
   :members:
   :undoc-members:
   :show-inheritance:

Schemas
-------

Pydantic request/response models (DTOs) for the HTTP API.

.. automodule:: veupath_chatbot.transport.http.schemas.chat
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.schemas.strategies
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.schemas.plan
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.schemas.sites
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.schemas.steps
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.schemas.experiments
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.schemas.health
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.schemas.veupathdb_auth
   :members:
   :undoc-members:
   :show-inheritance:
