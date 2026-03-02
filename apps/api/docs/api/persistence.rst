Persistence
===========

Database layer: SQLAlchemy models, session management, and repositories
for strategies and users. Used by the HTTP layer and background jobs.

Overview
--------

- **ORM Models** — Strategy, User, StrategyHistory. Map to PostgreSQL tables.
- **Session** — Async engine, session factory, init/close lifecycle.
- **Repositories** — StrategyRepository, UserRepository.
  Encapsulate queries and CRUD.

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
StrategyRepository: get, create, update, delete strategies.
UserRepository: users.

**Key classes:** :py:class:`StrategyRepository`

.. automodule:: veupath_chatbot.persistence.repo
   :members:
   :undoc-members:
   :show-inheritance:
