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
loading, site context. Used by chat, strategies, and plans routers.

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
