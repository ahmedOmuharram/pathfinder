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

Design Decisions
~~~~~~~~~~~~~~~~

.. dropdown:: Multi-source aggregation
   :icon: globe

   No single literature API has complete coverage.
   Semantic Scholar excels at recent ML/CS papers; PubMed covers biomedical
   literature; Europe PMC has open-access full text; OpenAlex provides broad
   citation data. PathFinder queries all sources in parallel and deduplicates
   by DOI/PMID, giving researchers the best coverage without requiring them to
   know which API to use.

.. dropdown:: Deduplication by DOI + PMID
   :icon: duplicate

   Papers appear in multiple databases. The
   literature search generates a dedupe key from DOI (preferred) or PMID, removing
   exact duplicates. Near-duplicates (different title casing, different abstract
   length) are handled by fuzzy matching on normalized title + first author.

.. dropdown:: DuckDuckGo for web search
   :icon: search

   DuckDuckGo's Instant Answer API requires no
   API key and has generous rate limits. It's used for general web queries when
   the agent needs non-academic information (documentation, protocols, methods).

.. list-table:: Supported Research Sources
   :widths: 25 25 50
   :header-rows: 1

   * - Source
     - Type
     - Coverage
   * - Semantic Scholar
     - Academic
     - CS, ML, biomedical — citation graphs
   * - PubMed
     - Academic
     - Biomedical literature (MEDLINE)
   * - Europe PMC
     - Academic
     - Open-access full text, preprints
   * - OpenAlex
     - Academic
     - Broad citation data, works metadata
   * - Crossref
     - Academic
     - DOI metadata, publisher data
   * - arXiv
     - Preprint
     - CS, math, physics, biology preprints
   * - DuckDuckGo
     - Web
     - General web search (no API key required)

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

API clients for literature sources. Each implements search for its backend.
All clients inherit from :py:class:`BaseClient` / :py:class:`StandardClient`
defined in the base module.

.. automodule:: veupath_chatbot.services.research.clients._base
   :members:
   :undoc-members:
   :show-inheritance:

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
