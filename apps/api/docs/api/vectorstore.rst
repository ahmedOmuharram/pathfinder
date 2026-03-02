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

.. automodule:: veupath_chatbot.integrations.vectorstore.qdrant_store
   :members:
   :undoc-members:
   :show-inheritance:

Bootstrap
---------

**Purpose:** Vectorstore initialization at API startup. Creates collections if
missing, runs migrations. Called when RAG is enabled and QDRANT_URL is set.

**Key function:** Startup entry point

.. automodule:: veupath_chatbot.integrations.vectorstore.bootstrap
   :members:
   :undoc-members:
   :show-inheritance:

Collections
-----------

**Purpose:** Qdrant collection definitions and schema. Defines the
embedding dimensions, distance metrics, and payload indices for each
collection (catalog, example_plans).

.. automodule:: veupath_chatbot.integrations.vectorstore.collections
   :members:
   :undoc-members:
   :show-inheritance:

Dependent Vocab Cache
---------------------

**Purpose:** Cache for dependent vocabulary lookups. Avoids repeated
WDK calls for parameter vocabularies that depend on other parameter values.

.. automodule:: veupath_chatbot.integrations.vectorstore.dependent_vocab_cache
   :members:
   :undoc-members:
   :show-inheritance:

Ingestion
---------

**Purpose:** Ingest data into the vectorstore. WDK catalog ingestion,
public strategy ingestion, and shared utilities.

.. automodule:: veupath_chatbot.integrations.vectorstore.ingest.wdk_catalog
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.integrations.vectorstore.ingest.public_strategies
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.integrations.vectorstore.ingest.public_strategies_helpers
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.integrations.vectorstore.ingest.utils
   :members:
   :undoc-members:
   :show-inheritance:
