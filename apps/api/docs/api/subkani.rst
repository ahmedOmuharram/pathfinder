Sub-kani Orchestration
======================

Sub-kanis are smaller agents spawned by the main executor to handle delegated
tasks. When the user requests a multi-step build (e.g. "find gametocyte genes
and subtract housekeeping"), the main agent calls ``delegate_strategy_subtasks``.
The orchestrator spawns one SubtaskAgent per task, runs them in dependency order,
and creates combine steps to link results.

Orchestrator
------------

**Purpose:** Implement the ``delegate_strategy_subtasks`` logic. Validates the
plan, spawns sub-agents, runs tasks with dependencies, creates combine steps,
emits subkani events.

**Key function:** :py:func:`veupath_chatbot.ai.subkani.orchestrator.delegate_strategy_subtasks`

**Flow:**

1. Build and validate :py:class:`veupath_chatbot.ai.delegation_plan.DelegationPlan` from the nested plan.
2. Create or get the strategy graph.
3. For each task node (in dependency order):
   - Run :py:func:`veupath_chatbot.ai.subkani.orchestrator.run_subkani_task` — spawn SubtaskAgent, pass dependency context.
   - Collect step IDs from results.
4. For each combine node, create the combine step via strategy_tools.
5. Emit ``subkani_task_start``, ``subkani_tool_call_*``, ``subkani_task_end``.

.. automodule:: veupath_chatbot.ai.subkani.orchestrator
   :members:
   :undoc-members:
   :show-inheritance:

Subtask Scheduler
-----------------

**Purpose:** Run task nodes with dependency ordering. Uses topological sort
so that nodes run only after their dependencies complete.

**Key functions:** :py:func:`veupath_chatbot.ai.subtask_scheduler.run_nodes_with_dependencies`, :py:func:`veupath_chatbot.ai.subtask_scheduler.partition_task_results`

.. automodule:: veupath_chatbot.ai.subtask_scheduler
   :members:
   :undoc-members:
   :show-inheritance:

Subkani Utils
-------------

**Purpose:** Helpers for subkani: format task context, extract step IDs from
results, consume subkani round output.

.. automodule:: veupath_chatbot.ai.subkani_utils
   :members:
   :undoc-members:
   :show-inheritance:
