Persistence
===========

Database layer: SQLAlchemy models, session management, and repositories
for strategies and users. Used by the HTTP layer and background jobs.

Overview
--------

- **ORM Models** — User, ControlSet, and related models. Map to PostgreSQL tables.
- **Session** — Async engine, session factory, init/close lifecycle.
- **Repositories** — UserRepository, StreamRepository, ControlSetRepository.
  Encapsulate queries and CRUD.

Design Decisions
~~~~~~~~~~~~~~~~

.. dropdown:: Async SQLAlchemy
   :icon: zap

   All database operations use ``async`` sessions with
   ``asyncpg`` (PostgreSQL's native async driver). This ensures the event loop
   is never blocked by database I/O, which matters for SSE streaming where many
   concurrent connections share the same process.

.. dropdown:: Repository pattern
   :icon: package

   Each domain entity (users, streams, control sets) has
   its own repository class that encapsulates queries. Services never construct
   raw SQL — they call repository methods. This makes testing easier (mock the
   repository, not the database) and keeps SQL details out of business logic.

.. dropdown:: Alembic for migrations
   :icon: versions

   Schema migrations use Alembic with async-compatible
   migration scripts. ``create_all`` is retained for development convenience
   (fresh databases), but production-like environments should use Alembic to
   apply schema changes incrementally.

.. dropdown:: UUID primary keys
   :icon: key

   All entities use UUID primary keys (via the custom
   ``GUID`` type decorator) for globally unique, non-sequential identifiers. This
   allows distributed ID generation without coordination and prevents information
   leakage from sequential IDs.

.. note::

   Schema migrations use **Alembic** (see ``alembic/versions/``).
   ``create_all`` is retained for development convenience on fresh databases.

ORM Models
----------

**Purpose:** SQLAlchemy models for strategies, users, and strategy history.
Define the schema and relationships.

**Key classes:** :py:class:`Strategy`, :py:class:`User`

.. automodule:: veupath_chatbot.persistence.models
   :members:
   :undoc-members:
   :show-inheritance:

Session Management
------------------

**Purpose:** Async engine, session factory, and lifecycle hooks (init, close).
Used by FastAPI dependency injection and background tasks.

**Key functions:** :py:func:`get_db_session`, :py:func:`init_db`, :py:func:`close_db`

.. automodule:: veupath_chatbot.persistence.session
   :members:
   :undoc-members:
   :show-inheritance:

Repositories
------------

**Purpose:** Data access layer. Encapsulates queries and CRUD operations.
Split into domain-specific repository modules.

.. automodule:: veupath_chatbot.persistence.repositories.user
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.persistence.repositories.stream
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.persistence.repositories.control_set
   :members:
   :undoc-members:
   :show-inheritance:
