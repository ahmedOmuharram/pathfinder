HTTP Transport
==============

FastAPI dependencies, SSE streaming, and HTTP-layer utilities. Connects
the HTTP API to the chat and strategy services.

Overview
--------

- **Dependencies** — Request-scoped deps: auth, DB session, repository injection.
  Injected into router handlers.
- **Streaming** — SSE (Server-Sent Events) for chat. Event formatting,
  chunk encoding, stream lifecycle.

Application Factory
-------------------

**Purpose:** FastAPI application entrypoint. Creates the app with middleware,
lifecycle management (database init, Redis), router registration, and
startup background tasks.

**Design:** The factory pattern (``create_app()``) enables testing with different
configurations and ensures clean setup/teardown of database connections and Redis
pools via FastAPI lifespan events.

.. automodule:: veupath_chatbot.main
   :members:
   :undoc-members:
   :show-inheritance:

Developer Tools
---------------

**Purpose:** Developer tooling for keeping the OpenAPI spec in sync with the
FastAPI application. Generates ``packages/spec/openapi.yaml`` and
``packages/shared-ts/src/openapi.generated.ts`` from the running app's schema.
This is intentionally NOT run at runtime — it writes repo files during
development.

.. automodule:: veupath_chatbot.devtools.openapi
   :members:
   :undoc-members:
   :show-inheritance:

Dependencies
------------

**Purpose:** FastAPI dependencies. Provide auth context, DB session, repository
injection, and experiment ownership checks. Used by routers.

**Key functions:** :py:func:`get_current_user_with_db_row`,
:py:func:`get_experiment_owned_by_user`

.. automodule:: veupath_chatbot.transport.http.deps
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

.. automodule:: veupath_chatbot.transport.http.routers.sites.catalog
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.sites.genes
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.sites.params
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

.. automodule:: veupath_chatbot.transport.http.routers.dev
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.exports
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.gene_sets
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.internal
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.operations
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.tools
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.user_data
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

.. automodule:: veupath_chatbot.transport.http.routers.experiments.chat
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.routers.experiments.results
   :members:
   :undoc-members:
   :show-inheritance:

Workbench Chat
--------------

**Purpose:** Workbench chat orchestration. Mirrors the main chat orchestrator
but scoped to (user_id, experiment_id) pairs for experiment-context conversations.

.. automodule:: veupath_chatbot.services.workbench_chat.orchestrator
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

.. automodule:: veupath_chatbot.transport.http.schemas.gene_sets
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.schemas.workbench_chat
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.schemas.optimization
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.schemas.sse
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.transport.http.schemas.experiment_responses
   :members:
   :undoc-members:
   :show-inheritance:
