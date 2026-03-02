Delegation Plans
================

A delegation plan is a nested binary tree that describes a multi-step strategy
build. The agent produces it when it has a concrete build approach and
consumes it via ``delegate_strategy_subtasks(goal, plan)``.

Plan Schema
-----------

**Task node** (creates one step via a sub-agent):

.. code-block:: text

   { "type": "task", "task": "<what to build>", "hint": "<optional>",
     "context": {}, "input": <optional child node> }

**Combine node** (binary operator; orchestrator creates after children complete):

.. code-block:: text

   { "type": "combine", "operator": "UNION"|"INTERSECT"|"MINUS"|"RMINUS"|"COLOCATE",
     "left": <node>, "right": <node> }

**Rules:**

- Plan must be a single nested tree. Top-level keys: ``goal`` and ``plan`` only.
- Combine nodes must have both ``left`` and ``right``.
- Task nodes run in dependency order (children before parents).
- The agent can save artifacts via ``save_planning_artifact`` to record
  research and proposed strategy plans before building.

Delegation Plan (Compiled)
--------------------------

:py:func:`veupath_chatbot.ai.orchestration.delegation.build_delegation_plan` normalizes and validates the model-produced
plan into a strict :py:class:`veupath_chatbot.ai.orchestration.delegation.DelegationPlan`:

- ``goal`` — User goal string.
- ``tasks`` — Flat list of task nodes (dependency order).
- ``combines`` — Combine nodes to create after tasks.
- ``nodes_by_id`` — Map node_id → node for lookups.
- ``dependents`` — Map node_id → list of IDs that depend on it.

If validation fails, returns an error payload (tool_error) instead of a
DelegationPlan.

.. automodule:: veupath_chatbot.ai.orchestration.delegation
   :members:
   :undoc-members:
   :show-inheritance:

Planning Artifacts
------------------

The agent can save planning artifacts via ``save_planning_artifact``:
title, summary markdown, assumptions, parameters, and an optional
``proposed_strategy_plan`` (delegation plan). Artifacts are embedded in
the strategy conversation messages.
