VEuPathDB Integrations
======================

Client, discovery, and strategy APIs for interacting with the VEuPathDB WDK
(Workspace Development Kit) REST API.

.. mermaid::

   flowchart TD
       PF["PathFinder Services"] --> F["Factory"]
       F -->|site_id| C["WDK Client"]
       F -->|site_id| D["Discovery Cache"]
       C --> API["VEuPathDB WDK REST API"]
       C --> SA["Strategy API"]
       SA --> Steps["Steps"]
       SA --> Strategies["Strategies"]
       SA --> Reports["Reports"]
       SA --> Records["Records"]

       style PF fill:#2563eb,color:#fff
       style API fill:#059669,color:#fff

Overview
--------

- **Strategy API** — Create steps, compose step trees, build strategies, run
  reports. The main interface for WDK strategy operations.
- **HTTP Client** — Low-level GET/POST with auth, retries, and JSON handling.
- **Discovery** — Cached catalog of record types and searches per site.
- **Factory** — Obtain configured clients and discovery services by site.

Design Decisions
~~~~~~~~~~~~~~~~

.. dropdown:: Cookie-based WDK auth
   :icon: key

   VEuPathDB's WDK API uses cookie-based sessions, not
   OAuth tokens. The HTTP client manages a ``JSESSIONID`` cookie jar per site,
   authenticating via the ``/login`` endpoint. This mirrors how WDK's browser-based
   UI authenticates, ensuring compatibility with all WDK endpoints.

.. dropdown:: Factory pattern for multi-site support
   :icon: server

   PathFinder supports ~15 VEuPathDB
   sites (PlasmoDB, TriTrypDB, FungiDB, etc.). The factory creates per-site clients
   with the correct base URL, cookie jar, and discovery cache. Services request a
   client by ``site_id`` rather than managing URLs directly.

.. dropdown:: Strategy API split
   :icon: git-branch

   The WDK Strategy API is split into focused submodules
   (steps, strategies, reports, records, analyses, filters) rather than a monolithic
   client. Each submodule handles one concern, making it easier to test and modify
   individual operations without touching the rest.

Strategy API
------------

**Purpose:** Create and manage WDK steps and strategies. Implements the WDK REST
pattern: create unattached steps via POST, compose a tree via ``stepTree``,
then build the strategy.

**Key classes and functions:**

- :py:class:`StrategyAPI` — Main API; methods: ``create_step``, ``create_combined_step``,
  ``build_strategy``, ``get_step_count``, ``get_step_answer``
- :py:class:`StepTreeNode` — Tree node for step composition (defined in ``domain.strategy.ast``,
  re-exported from ``strategy_api.helpers``)
- :py:func:`is_internal_wdk_strategy_name` — Check if strategy is a Pathfinder helper (in ``helpers``)
- :py:func:`strip_internal_wdk_strategy_name` — Remove internal name prefix (in ``helpers``)

.. automodule:: veupath_chatbot.integrations.veupathdb.strategy_api.api
   :members:
   :undoc-members:
   :show-inheritance:

HTTP Client
-----------

**Purpose:** Low-level HTTP client for VEuPathDB WDK endpoints. Handles auth,
request formatting, response parsing, and retries.

**Key class:** :py:class:`VEuPathDBClient` — methods: ``get``, ``post``, ``put``,
``patch``, ``delete``; search details and report execution helpers.

.. automodule:: veupath_chatbot.integrations.veupathdb.client
   :members:
   :undoc-members:
   :show-inheritance:

Discovery
---------

**Purpose:** Cached catalog of record types, searches, and parameter specs per
site. Used by tools to discover available questions and parameters without
repeated WDK calls.

**Key class:** :py:class:`SearchCatalog` — ``load``, ``get_record_types``,
``get_searches``, ``get_search_details``

.. automodule:: veupath_chatbot.integrations.veupathdb.discovery
   :members:
   :undoc-members:
   :show-inheritance:

Factory
-------

**Purpose:** Factory for obtaining configured VEuPathDB clients and discovery
services. Manages site routing and client lifecycle.

**Key function:** :py:func:`get_wdk_client`

.. note::

   :py:func:`get_discovery_service` is defined in ``integrations.veupathdb.discovery``,
   not in the factory module.

.. automodule:: veupath_chatbot.integrations.veupathdb.factory
   :members:
   :undoc-members:
   :show-inheritance:

Strategy API — Submodules
-------------------------

The Strategy API is split into focused submodules for steps, strategies,
reports, and shared helpers.

.. automodule:: veupath_chatbot.integrations.veupathdb.strategy_api.base
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.integrations.veupathdb.strategy_api.steps
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.integrations.veupathdb.strategy_api.strategies
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.integrations.veupathdb.strategy_api.reports
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.integrations.veupathdb.strategy_api.helpers
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.integrations.veupathdb.strategy_api.analyses
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.integrations.veupathdb.strategy_api.filters
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.integrations.veupathdb.strategy_api.records
   :members:
   :undoc-members:
   :show-inheritance:

Parameter Utils
---------------

**Purpose:** Parameter parsing and formatting utilities for WDK parameter specs.

.. automodule:: veupath_chatbot.integrations.veupathdb.param_utils
   :members:
   :undoc-members:
   :show-inheritance:

Site Router
-----------

**Purpose:** Route requests to the correct VEuPathDB site by site ID.
Manages site URL mappings.

.. automodule:: veupath_chatbot.integrations.veupathdb.site_router
   :members:
   :undoc-members:
   :show-inheritance:

Site Search
-----------

**Purpose:** Site-level search across VEuPathDB. Used for gene lookup
and catalog discovery.

.. automodule:: veupath_chatbot.integrations.veupathdb.site_search
   :members:
   :undoc-members:
   :show-inheritance:

Temporary Results
-----------------

**Purpose:** Create and manage temporary WDK results for step reports,
downloads, and analysis. Handles user session resolution.

.. automodule:: veupath_chatbot.integrations.veupathdb.temporary_results
   :members:
   :undoc-members:
   :show-inheritance:

