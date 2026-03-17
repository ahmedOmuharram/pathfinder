Agents
======

Pathfinder uses two Kani-based agents: the main unified agent and
sub-agents for delegated tasks. Both extend `Kani <https://github.com/zhudotexe/kani>`_
with tools and prompts tailored to VEuPathDB strategy building.

.. list-table:: Agent Comparison
   :widths: 20 25 25 30
   :header-rows: 1

   * - Agent
     - Purpose
     - Tools
     - When Used
   * - **PathfinderAgent**
     - Unified chat agent
     - All tools (catalog, strategy, research, delegation)
     - Every chat conversation
   * - **SubtaskAgent**
     - Delegated sub-task
     - Same minus delegation
     - Multi-step builds via sub-kani
   * - **ExperimentAssistantAgent**
     - Experiment wizard helper
     - Research + catalog + gene lookup
     - ``POST /api/v1/experiments/ai-assist``
   * - **WorkbenchAgent**
     - Workbench analysis chat
     - 7 tool mixins (research, gene, catalog, refinement, analysis, workbench)
     - Workbench conversations

PathfinderAgent (Unified)
-------------------------

**Purpose:** The single agent for all conversations. Handles research (catalog
exploration, literature search, control tests, optimization) and execution
(graph building, strategy composition) in a unified tool set. The model
decides per-turn which capabilities to use. For multi-step builds, delegates
to sub-kanis.

**Inherits:** :py:class:`veupath_chatbot.ai.tools.unified_registry.UnifiedToolRegistryMixin`, ``Kani``

**Tools:** Catalog (list_sites, get_record_types, search_for_searches, etc.),
strategy tools (create_step, list_current_steps, build_strategy, delete_step,
update_step, etc.), conversation tools (save_strategy, load_strategy),
research (web_search, literature_search), validation (run_control_tests,
optimize_search_parameters, lookup_gene_records), artifacts
(save_planning_artifact), and **delegate_strategy_subtasks**.

.. tip::

   The unified agent has no separate "plan mode" or "execute mode". The model
   autonomously decides per-turn whether to research, plan, or build. This
   matches how researchers naturally describe goals.

.. automodule:: veupath_chatbot.ai.agents.executor
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

**When used:** Internally by :py:func:`veupath_chatbot.ai.orchestration.subkani.orchestrator.delegate_strategy_subtasks` for each
task node in the delegation plan.

.. automodule:: veupath_chatbot.ai.agents.subtask
   :members:
   :undoc-members:
   :show-inheritance:

ExperimentAssistantAgent
------------------------

**Purpose:** Lightweight AI assistant for the workbench experiment wizard.
Scoped to research capabilities (web search, literature search, catalog tools,
gene lookup) for helping users configure experiment steps.

**Inherits:** :py:class:`~veupath_chatbot.ai.tools.research_registry.ResearchToolsMixin`, ``Kani``

**Tools:** web_search, literature_search, catalog tools, gene lookup. No strategy
mutation or delegation tools.

**When used:** By the experiment wizard AI-assist endpoint
(``POST /api/v1/experiments/ai-assist``).

.. automodule:: veupath_chatbot.ai.agents.experiment
   :members:
   :undoc-members:
   :show-inheritance:

WorkbenchAgent
--------------

**Purpose:** Full-featured conversational AI agent for the workbench. Provides
experiment result exploration, gene set analysis, strategy refinement, and
literature research within the context of a specific experiment.

**Inherits:** Composes 7 tool mixins (research, gene, catalog, refinement,
analysis, workbench read, workbench mutation) + ``Kani``

**When used:** By the workbench chat endpoint, scoped to a (user_id, experiment_id) pair.

.. automodule:: veupath_chatbot.ai.agents.workbench
   :members:
   :undoc-members:
   :show-inheritance:

Agent Factory
-------------

**Purpose:** Build the agent with the right engine and model. Resolves model ID
from override, persisted state, or server default.

See :doc:`ai` for full reference.
