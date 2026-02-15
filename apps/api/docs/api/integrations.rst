VEuPathDB Integrations
======================

Client, discovery, and strategy APIs for interacting with the VEuPathDB WDK
(Workspace Development Kit) REST API.

Overview
--------

- **Strategy API** — Create steps, compose step trees, build strategies, run
  reports. The main interface for WDK strategy operations.
- **HTTP Client** — Low-level GET/POST with auth, retries, and JSON handling.
- **Discovery** — Cached catalog of record types and searches per site.
- **Factory** — Obtain configured clients and discovery services by site.

Strategy API
------------

**Purpose:** Create and manage WDK steps and strategies. Implements the WDK REST
pattern: create unattached steps via POST, compose a tree via ``stepTree``,
then build the strategy.

**Key classes and functions:**

- :py:class:`StrategyAPI` — Main API; methods: ``create_step``, ``create_combined_step``,
  ``build_strategy``, ``get_step_count``, ``get_step_answer``
- :py:class:`StepTreeNode` — Tree node for step composition
- :py:func:`is_internal_wdk_strategy_name` — Check if strategy is a Pathfinder helper
- :py:func:`strip_internal_wdk_strategy_name` — Remove internal name prefix

.. automodule:: veupath_chatbot.integrations.veupathdb.strategy_api
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

**Key functions:** :py:func:`get_wdk_client`, :py:func:`get_discovery_service`

.. automodule:: veupath_chatbot.integrations.veupathdb.factory
   :members:
   :undoc-members:
   :show-inheritance:
