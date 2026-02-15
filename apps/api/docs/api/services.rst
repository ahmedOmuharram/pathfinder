Services
========

Core business logic for gene lookup, parameter optimization, control tests,
and catalog access. Services are stateless and orchestrated by the chat layer.

Overview
--------

- **Gene lookup** — Resolve gene names/symbols to VEuPathDB IDs via site-search
  or the WDK stateless reporter. Used when the user mentions genes from literature.
- **Parameter optimization** — Optimize search parameters against positive/negative
  control lists using Bayesian optimization (TPE), grid, or random search.
- **Control tests** — Run temporary WDK strategies with known gene lists and
  compute precision, recall, F1. Used by optimization and validation.
- **Catalog** — Get parameter specs, validate values, list sites/searches.
- **Strategy session** — Load and merge strategy state with conversation messages.

Gene Lookup
-----------

**Purpose:** Resolve gene names and IDs via VEuPathDB site-search and the WDK
stateless reporter. Used by the planner to validate gene references from
literature or user input.

**Key functions:**

- :py:func:`lookup_genes_by_text` — Search by free text (name, symbol, description)
- :py:func:`resolve_gene_ids` — Resolve a list of known IDs to full records via WDK

.. automodule:: veupath_chatbot.services.gene_lookup
   :members:
   :undoc-members:
   :show-inheritance:

Parameter Optimization
----------------------

**Purpose:** Optimize search parameters against positive/negative control gene
lists using Bayesian optimization (TPE), grid search, or random search. Each
trial runs a temporary WDK strategy and scores the result.

**Key types:** ``ParameterSpec``, ``OptimizationConfig``, ``OptimizationResult``

.. automodule:: veupath_chatbot.services.parameter_optimization
   :members:
   :undoc-members:
   :show-inheritance:

Control Tests
-------------

**Purpose:** Run positive/negative control gene lists against a WDK strategy
and compute precision, recall, F1, and related metrics. Used by parameter
optimization and for validation.

**Key function:** :py:func:`run_positive_negative_controls`

.. automodule:: veupath_chatbot.services.control_tests
   :members:
   :undoc-members:
   :show-inheritance:

Catalog (Parameters & Searches)
--------------------------------

**Purpose:** Retrieve and validate search parameters from VEuPathDB. Handles
parameter specs, dependent vocabularies, and search details. Used by tools
when the agent needs to discover or validate parameters.

**Key functions:**

- :py:func:`get_search_parameters` — Full parameter specs for a search
- :py:func:`validate_search_params` — Validate parameter values
- :py:func:`get_dependent_vocab` — Refresh dependent parameter options

.. automodule:: veupath_chatbot.services.catalog.parameters
   :members:
   :undoc-members:
   :show-inheritance:

Catalog (Sites & Record Types)
------------------------------

**Purpose:** Sites, record types, and search listing. Entry point for discovery.

.. automodule:: veupath_chatbot.services.catalog.sites
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.catalog.searches
   :members:
   :undoc-members:
   :show-inheritance:

Strategy Session
----------------

**Purpose:** Load and merge strategy state with conversation messages. Used
when switching strategies or restoring sessions.

.. automodule:: veupath_chatbot.services.strategy_session
   :members:
   :undoc-members:
   :show-inheritance:
