Agents
======

Pathfinder uses three Kani-based agents: the main executor, the planner, and
sub-agents for delegated tasks. All extend `Kani <https://github.com/zhudotexe/kani>`_
with tools and prompts tailored to VEuPathDB strategy building.

PathfinderAgent (Execute Mode)
------------------------------

**Purpose:** The main agent when a strategy is attached. Builds and edits the
strategy graph via tools. For multi-step builds, delegates to sub-kanis.

**Inherits:** :py:class:`veupath_chatbot.ai.tools.registry.AgentToolRegistryMixin`, ``Kani``

**Tools:** Catalog (list_sites, get_record_types, search_for_searches, etc.),
strategy tools (create_step, list_current_steps, build_strategy, delete_step,
update_step, etc.), conversation tools (save_strategy, load_strategy),
research (web_search, literature_search), and **delegate_strategy_subtasks**.

**When to use:** ``mode="execute"`` — user has a strategy and wants to build/edit it.

.. automodule:: veupath_chatbot.ai.agent_runtime
   :members:
   :undoc-members:
   :show-inheritance:

PathfinderPlannerAgent (Plan Mode)
----------------------------------

**Purpose:** Agent when no strategy is attached. Explores the catalog, runs
control tests, optimizes parameters, saves planning artifacts and delegation
drafts. When confident, calls ``request_executor_build`` to hand off to the executor.

**Inherits:** :py:class:`veupath_chatbot.ai.tools.planner_registry.PlannerToolRegistryMixin`, ``Kani``

**Tools:** Catalog exploration, ``save_planning_artifact``, ``save_delegation_plan_draft``,
``request_executor_build``, ``run_control_tests``, ``optimize_search_parameters``,
``lookup_gene_records``, research. No graph-building tools (create_step, etc.).

**When to use:** ``mode="plan"`` — user is exploring, planning, or validating.

.. automodule:: veupath_chatbot.ai.planner_runtime
   :members:
   :undoc-members:
   :show-inheritance:

SubtaskAgent (Sub-kani)
-----------------------

**Purpose:** Sub-agent spawned by the orchestrator for one delegated task. Has
the same tools as the main agent (catalog, strategy) but **no** delegation.
Each sub-kani creates exactly one step (or edits one) and returns the result.

**Inherits:** :py:class:`veupath_chatbot.ai.tools.registry.AgentToolRegistryMixin`, ``Kani``

**Tools:** Same as PathfinderAgent minus ``delegate_strategy_subtasks``.

**When used:** Internally by :py:func:`veupath_chatbot.ai.subkani.orchestrator.delegate_strategy_subtasks` for each
task node in the delegation plan.

.. automodule:: veupath_chatbot.ai.subtask_agent
   :members:
   :undoc-members:
   :show-inheritance:

Agent Factory
-------------

**Purpose:** Build the correct agent (planner or executor) with the right engine
and model. Resolves model ID from override, persisted state, or server default.

See :doc:`ai` for full reference.
