Delegation Plans
================

A delegation plan is a nested binary tree that describes a multi-step strategy
build. The planner produces it when the user has agreed on an approach. The
executor consumes it via ``delegate_strategy_subtasks(goal, plan)``.

Plan Schema
-----------

**Task node** (creates one step via a sub-agent):

.. code-block:: text

   { "type": "task", "task": "<what to build>", "hint": "<optional>",
     "context": {}, "input": <optional child node> }

**Combine node** (binary operator; orchestrator creates after children complete):

.. code-block:: text

   { "type": "combine", "operator": "UNION"|"INTERSECT"|"MINUS_LEFT"|"MINUS_RIGHT"|"COLOCATE",
     "left": <node>, "right": <node> }

**Rules:**

- Plan must be a single nested tree. Top-level keys: ``goal`` and ``plan`` only.
- Combine nodes must have both ``left`` and ``right``.
- Task nodes run in dependency order (children before parents).
- The planner saves drafts via ``save_delegation_plan_draft`` and hands off via
  ``request_executor_build`` when ready.

Delegation Plan (Compiled)
--------------------------

:py:func:`veupath_chatbot.ai.delegation_plan.build_delegation_plan` normalizes and validates the model-produced
plan into a strict :py:class:`veupath_chatbot.ai.delegation_plan.DelegationPlan`:

- ``goal`` — User goal string.
- ``tasks`` — Flat list of task nodes (dependency order).
- ``combines`` — Combine nodes to create after tasks.
- ``nodes_by_id`` — Map node_id → node for lookups.
- ``dependents`` — Map node_id → list of IDs that depend on it.

If validation fails, returns an error payload (tool_error) instead of a
DelegationPlan.

.. automodule:: veupath_chatbot.ai.delegation_plan
   :members:
   :undoc-members:
   :show-inheritance:

Plan Session Artifacts
----------------------

The planner saves:

- **Planning artifacts** — ``save_planning_artifact``: title, summary markdown,
  assumptions, parameters, optional ``proposed_strategy_plan`` (delegation plan).
- **Delegation draft** — ``save_delegation_plan_draft``: iterative draft of the
  delegation plan. Updated as the user answers questions. When ready,
  ``request_executor_build`` loads the draft and hands off to the executor.
