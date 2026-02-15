AI Tools
========

Tool registration mixins and registries exposed to the agent. These define
the catalog, planner, and execution tools available during chat. Each tool
is an ``@ai_function()`` that the LLM can call.

Overview
--------

- **Catalog & Registry** — Execute-mode tools: list sites, record types,
  searches; get parameters; dependent vocab; graph-building operations.
- **Planner Registry** — Plan-mode tools: catalog exploration, example plans,
  planning artifacts, optimize_search_parameters, executor build request.
- **Research Registry** — Web search and literature search (shared by both modes).
- **Execution Tools** — Parse tool args, apply graph snapshots, build strategy.

Catalog & Registry
------------------

**Purpose:** Base tool registry for execute mode. Provides catalog discovery
(record types, searches, parameters), dependent vocab, and graph-building tools.
Each tool returns combined RAG + WDK results when both are available.

**Key methods (on AgentToolRegistryMixin):** ``list_sites``, ``get_record_types``,
``list_searches``, ``get_search_parameters``, ``get_dependent_vocab``, plus
strategy tools for create_step, list_current_steps, build_strategy, etc.

.. automodule:: veupath_chatbot.ai.tools.registry
   :members:
   :undoc-members:
   :show-inheritance:

Planner Registry
----------------

**Purpose:** Planner-mode tools: catalog exploration, example plans, planning
artifacts, optimize_search_parameters, and executor build request. Used when
the user is exploring data without an attached strategy.

**Key methods:** ``search_for_searches``, ``search_example_plans``,
``optimize_search_parameters``, ``request_executor_build``

.. automodule:: veupath_chatbot.ai.tools.planner_registry
   :members:
   :undoc-members:
   :show-inheritance:

Research Registry
-----------------

**Purpose:** Research tools mixin: web search and literature search. Used by
both planner and execute registries. Provides ``web_search`` and
``literature_search`` tools.

.. automodule:: veupath_chatbot.ai.tools.research_registry
   :members:
   :undoc-members:
   :show-inheritance:

Execution Tools
---------------

**Purpose:** Execute-mode tool wiring: parse tool arguments from LLM output,
apply graph snapshots from tool results, build strategy. Used when the agent
runs in execute mode and needs to interpret create_step/build_strategy results.

**Key functions:** :py:func:`parse_tool_arguments`, :py:func:`parse_tool_result`,
:py:func:`apply_graph_snapshot_from_tool_result`

.. automodule:: veupath_chatbot.ai.tools.execution_tools
   :members:
   :undoc-members:
   :show-inheritance:
