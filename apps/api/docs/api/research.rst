Research Services
=================

Web search and literature search. Integrates with DuckDuckGo, Semantic Scholar,
Europe PMC, Crossref, OpenAlex, PubMed, arXiv, and preprint servers. Used by
the ``web_search`` and ``literature_search`` tools.

Overview
--------

- **Literature Search** — Orchestrates multiple APIs; deduplication, filtering,
  ranking. Returns citations with DOIs, PMIDs, authors.
- **Web Search** — DuckDuckGo for general web queries.
- **Research Utils** — Text normalization, fuzzy scoring, deduplication, filters.
- **Clients** — Per-source API clients (Semantic Scholar, PubMed, etc.).

Literature Search
-----------------

**Purpose:** Orchestrates multiple literature APIs to find papers by query.
Handles deduplication, filtering, and ranking across sources. Returns citations
with DOI, PMID, authors, abstract.

**Key class:** :py:class:`LiteratureSearchService` — method: :py:meth:`search`

.. automodule:: veupath_chatbot.services.research.literature_search
   :members:
   :undoc-members:
   :show-inheritance:

Web Search
----------

**Purpose:** DuckDuckGo-based web search for general queries. Used when the
agent needs to look up external information.

**Key class:** :py:class:`WebSearchService`

.. automodule:: veupath_chatbot.services.research.web_search
   :members:
   :undoc-members:
   :show-inheritance:

Research Utils
--------------

**Purpose:** Utility functions for research: text normalization, author
limiting, fuzzy scoring, deduplication keys, filter predicates. Used by
literature search and citation processing.

**Key functions:** :py:func:`passes_filters`, :py:func:`dedupe_key`,
:py:func:`rerank_score`, :py:func:`norm_text`

.. automodule:: veupath_chatbot.services.research.utils
   :members:
   :undoc-members:
   :show-inheritance:

Research Clients
----------------

API clients for literature sources. Each implements search for its backend:

.. automodule:: veupath_chatbot.services.research.clients.semanticscholar
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.research.clients.europepmc
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.research.clients.pubmed
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.research.clients.crossref
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.research.clients.openalex
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.research.clients.arxiv
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.research.clients.preprint
   :members:
   :undoc-members:
   :show-inheritance:
