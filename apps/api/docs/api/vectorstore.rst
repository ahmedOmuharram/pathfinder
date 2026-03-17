Vectorstore
===========

Qdrant-based vector storage for RAG. Embeddings, collections, and ingestion.
Used for catalog and example-plan semantic retrieval when RAG is enabled.

.. mermaid::

   flowchart LR
       Q["User Query"] --> E["Embed (OpenAI)"]
       E --> S["Search Qdrant"]
       S --> T["Threshold Filter"]
       T --> P["Prune & Rank"]
       P --> R["Agent Context"]

       style Q fill:#2563eb,color:#fff
       style R fill:#059669,color:#fff

Overview
--------

- **Qdrant Store** — Client wrapper. Collection management, point upsert,
  similarity search. Powers catalog_rag and example_plans_rag tools.
- **Bootstrap** — Initialize vectorstore at startup. Create collections,
  run migrations. Called when RAG is enabled.

Design Decisions
~~~~~~~~~~~~~~~~

.. dropdown:: Why Qdrant for RAG?
   :icon: database

   Qdrant is a purpose-built vector database with native
   filtering, payload storage, and similarity search. For PathFinder's use case
   (semantic search over ~2000 WDK searches and ~500 public strategies), Qdrant
   provides fast approximate nearest-neighbor search without the overhead of
   managing a general-purpose database extension (like pgvector).

.. dropdown:: Two-collection design
   :icon: stack

   The vectorstore uses two collections: ``catalog``
   (record types + searches) and ``example_plans`` (public strategies). Separating
   them allows independent ingestion cycles (catalog changes rarely; example plans
   grow over time) and different embedding strategies (catalog entries use search
   descriptions; plans use strategy summaries).

.. dropdown:: Incremental ingestion
   :icon: sync

   The startup ingestion job checks existing point IDs
   before upserting, avoiding re-embedding unchanged data. This makes startup fast
   (typically < 5 seconds) while keeping the vectorstore up-to-date with catalog
   changes.

.. dropdown:: OpenAI embeddings
   :icon: cpu

   PathFinder uses ``text-embedding-3-small`` (1536
   dimensions) for all embeddings. This model provides good quality at low cost
   and is compatible with Qdrant's cosine similarity search.

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
