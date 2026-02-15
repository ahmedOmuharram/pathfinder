Vectorstore
===========

Qdrant-based vector storage for RAG. Embeddings, collections, and ingestion.
Used for catalog and example-plan semantic retrieval when RAG is enabled.

Overview
--------

- **Qdrant Store** — Client wrapper. Collection management, point upsert,
  similarity search. Powers catalog_rag and example_plans_rag tools.
- **Bootstrap** — Initialize vectorstore at startup. Create collections,
  run migrations. Called when RAG is enabled.

Qdrant Store
------------

**Purpose:** Qdrant client wrapper. Manages collections (e.g. catalog, example_plans),
upserts points with embeddings, runs similarity search. Used for RAG retrieval
when the agent explores the catalog or example plans.

**Key methods:** Collection operations, search, point upsert

.. automodule:: veupath_chatbot.services.vectorstore.qdrant_store
   :members:
   :undoc-members:
   :show-inheritance:

Bootstrap
---------

**Purpose:** Vectorstore initialization at API startup. Creates collections if
missing, runs migrations. Called when RAG is enabled and QDRANT_URL is set.

**Key function:** Startup entry point

.. automodule:: veupath_chatbot.services.vectorstore.bootstrap
   :members:
   :undoc-members:
   :show-inheritance:
