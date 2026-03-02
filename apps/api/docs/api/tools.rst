AI Tools
========

Tool registration mixins and registries exposed to the agent. These define
the catalog, research, validation, and execution tools available during chat.
Each tool is an ``@ai_function()`` that the LLM can call.

Overview
--------

- **Unified Registry** — Combines all tool mixins (catalog, strategy, research,
  validation, optimization, artifacts) into a single registry for the unified agent.
- **Catalog & Registry** — Catalog discovery and graph-building tools.
- **Research Registry** — Web search and literature search (shared tools).
- **Execution Tools** — Parse tool args, apply graph snapshots, build strategy.

Unified Registry
----------------

**Purpose:** Combined tool registry for the unified agent. Merges the catalog,
strategy, research, validation, optimization, and artifact tools into a single
mixin so the agent can use all capabilities per-turn.

.. automodule:: veupath_chatbot.ai.tools.unified_registry
   :members:
   :undoc-members:
   :show-inheritance:

Catalog & Registry
------------------

**Purpose:** Base tool registry. Provides catalog discovery (record types,
searches, parameters), dependent vocab, and graph-building tools.
Each tool returns combined RAG + WDK results when both are available.

**Key methods (on AgentToolRegistryMixin):** ``list_sites``, ``get_record_types``,
``list_searches``, ``get_search_parameters``, ``get_dependent_vocab``, plus
strategy tools for create_step, list_current_steps, build_strategy, etc.

.. automodule:: veupath_chatbot.ai.tools.registry
   :members:
   :undoc-members:
   :show-inheritance:

Research Registry
-----------------

**Purpose:** Research tools mixin: web search and literature search. Provides
``web_search`` and ``literature_search`` tools.

.. automodule:: veupath_chatbot.ai.tools.research_registry
   :members:
   :undoc-members:
   :show-inheritance:

Execution Tools
---------------

**Purpose:** Tool wiring: parse tool arguments from LLM output, apply graph
snapshots from tool results, build strategy. Used when the agent needs to
interpret create_step/build_strategy results.

**Key functions:** :py:func:`parse_tool_arguments`, :py:func:`parse_tool_result`,
:py:func:`apply_graph_snapshot_from_tool_result`

.. automodule:: veupath_chatbot.ai.tools.execution_tools
   :members:
   :undoc-members:
   :show-inheritance:

Catalog Tools
-------------

**Purpose:** Catalog discovery tools: site listing, record types, search queries,
parameter specs. Called by the agent to explore VEuPathDB data.

.. automodule:: veupath_chatbot.ai.tools.catalog_tools
   :members:
   :undoc-members:
   :show-inheritance:

Catalog RAG Tools
-----------------

**Purpose:** RAG-augmented catalog tools. Semantic search over the embedded
VEuPathDB catalog for record types and searches.

.. automodule:: veupath_chatbot.ai.tools.catalog_rag_tools
   :members:
   :undoc-members:
   :show-inheritance:

Example Plans RAG Tools
-----------------------

**Purpose:** RAG retrieval of example strategy plans. Helps the agent suggest
plan structures based on similar prior plans.

.. automodule:: veupath_chatbot.ai.tools.example_plans_rag_tools
   :members:
   :undoc-members:
   :show-inheritance:

Conversation Tools
------------------

**Purpose:** Conversation management tools: save/load strategy, update name,
session control. Used by the agent to manage the user's session.

.. automodule:: veupath_chatbot.ai.tools.conversation_tools
   :members:
   :undoc-members:
   :show-inheritance:

Query Validation
----------------

**Purpose:** Validate tool arguments and queries before execution. Catch
malformed inputs before they reach WDK.

.. automodule:: veupath_chatbot.ai.tools.query_validation
   :members:
   :undoc-members:
   :show-inheritance:

Agent Tool Submodules
---------------------

Individual tool modules for artifact management, gene lookup, optimization,
and experiment tools. These are mixed into the unified agent via
:py:class:`~veupath_chatbot.ai.tools.unified_registry.UnifiedToolRegistryMixin`.

.. automodule:: veupath_chatbot.ai.tools.planner.artifact_tools
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.ai.tools.planner.experiment_tools
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.ai.tools.planner.gene_tools
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.ai.tools.planner.optimization_tools
   :members:
   :undoc-members:
   :show-inheritance:

Strategy Tool Submodules
------------------------

Individual strategy tool modules for step creation, graph building,
attachment operations, discovery, and editing.

.. automodule:: veupath_chatbot.ai.tools.strategy_tools.step_ops
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.ai.tools.strategy_tools.graph_ops
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.ai.tools.strategy_tools.edit_ops
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.ai.tools.strategy_tools.discovery_ops
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.ai.tools.strategy_tools.attachment_ops
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.ai.tools.strategy_tools.operations
   :members:
   :undoc-members:
   :show-inheritance:
