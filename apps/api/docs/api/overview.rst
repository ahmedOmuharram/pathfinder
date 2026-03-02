Architecture Overview
=====================

This document describes the Pathfinder API architecture: how Kani drives the
unified agent, the **Experiment Lab** (separate from chat), sub-kani
orchestration, delegation plans, and the end-to-end request flow.

Application Areas
-----------------

Pathfinder has two main user-facing areas:

1. **Chat** (home page) — A single unified agent for building/editing strategy
   graphs via natural language. Every conversation is backed by a strategy.
   Uses ``POST /api/v1/chat``. The agent decides when to research (explore
   the catalog, search literature, run control tests) versus execute
   (build steps, compose strategies). Supports **@-mentions** of strategies
   and experiments (see :ref:`overview-mentions`).

2. **Experiment Lab** (``/experiments`` page) — Evaluate search/strategy
   performance with control sets, metrics, cross-validation, enrichment, and
   step analysis. Not a chat mode; it has its own setup flows and endpoints.
   Experiment **modes** are: **single** (one search), **multi-step** (strategy
   graph), **import** (existing WDK strategy). See :doc:`experiments` for
   endpoints and flows.

High-Level Chat Flow
--------------------

::

  HTTP Request (POST /api/v1/chat)
       │
       ▼
  Chat Orchestrator (start_chat_stream)
       │
       ▼
  PathfinderAgent (unified)  ──► All tools (catalog, research, graph building, artifacts, optimization)
       │
       │  when multi-step build
       ▼
  delegate_strategy_subtasks
       │
       ▼
  Sub-kani Orchestrator
       │
       ├── Spawn SubtaskAgent(s) for each task node
       ├── Run with dependency order (left before right, etc.)
       └── Emit subkani_task_start/end, tool_call events

What Kani Does
--------------

**Kani** is the agent framework we use. It provides:

- **Engine abstraction** — Swap OpenAI, Anthropic, or Google models without
  changing agent code. Each engine handles API calls, token counting, streaming.
- **Tool registration** — Methods decorated with ``@ai_function()`` become tools
  the LLM can call. Kani parses tool arguments from the model output and
  invokes the corresponding Python function.
- **Streaming** — Kani streams tokens, tool calls, and structured events.
  We wrap this into our SSE contract (message_start, tool_call_start, etc.).
- **Chat history** — Kani manages the message list (system, user, assistant)
  and injects tool results between turns.

Pathfinder extends Kani with:

- :py:class:`veupath_chatbot.ai.agents.executor.PathfinderAgent` — Unified agent; handles research, planning, and
  strategy building with a single tool set.
- :py:class:`veupath_chatbot.ai.agents.subtask.SubtaskAgent` — Sub-agent for delegated tasks; same tools as main
  agent minus delegation.

Unified Agent
-------------

There is a single ``PathfinderAgent`` that handles every conversation. The
model decides per-turn whether to research (explore the catalog, search
literature, run control tests, optimize parameters) or execute (build steps,
compose strategies). Every conversation is backed by a strategy.

**Tools available to the unified agent:**

- **Catalog / discovery:** ``list_sites``, ``search_for_searches``,
  ``get_search_parameters``, ``get_dependent_vocab``, etc.
- **Graph building / editing:** ``create_step``, ``list_current_steps``,
  ``build_strategy``, ``delete_step``, ``update_step``, etc.
- **Research / validation:** ``web_search``, ``literature_search``,
  ``run_control_tests``, ``optimize_search_parameters``,
  ``lookup_gene_records``, ``save_planning_artifact``.
- **Delegation:** ``delegate_strategy_subtasks`` for multi-step builds.

For **single-step** builds, the agent calls tools directly.
For **multi-step** builds (2+ steps, combines, transforms), the agent
calls ``delegate_strategy_subtasks(goal, plan)``, which spawns sub-kanis.

Sub-kani Orchestration
----------------------

When the agent receives a multi-step build request, it delegates to
**sub-kanis** — smaller Kani agents that each handle one task (e.g. "find
gametocyte gene search", "create step with fold_change=2").

**Flow:**

1. Main agent calls ``delegate_strategy_subtasks(goal, plan)``.
2. Orchestrator validates and normalizes the ``plan`` into a
   :py:class:`veupath_chatbot.ai.orchestration.delegation.DelegationPlan` (tasks + combines + dependencies).
3. For each task node (in dependency order), spawn a :py:class:`veupath_chatbot.ai.agents.subtask.SubtaskAgent`.
4. Sub-agent receives task description, dependency context (results from
   upstream tasks), and runs tools to create the step.
5. Orchestrator creates any combine/transform steps that link sub-agent
   outputs.
6. Emit ``subkani_task_start``, ``subkani_tool_call_start/end``, ``subkani_task_end``
   so the UI can show Sub-kani Activity.

**SubtaskAgent** — Same tool set as main agent (catalog, strategy tools) but
no ``delegate_strategy_subtasks``. Each sub-kani runs one delegated task.

**Subtask scheduler** — ``run_nodes_with_dependencies`` runs task nodes in
topological order. ``partition_task_results`` groups outputs for combine steps.

Delegation Plans
----------------

A **delegation plan** is a nested binary tree that mirrors the final strategy:

- **Task node** — ``{ "type": "task", "task": "<what to build>", "hint": "...", "context": {...}, "input": <child> }``
  Each task becomes one sub-kani run. The sub-agent creates one step.
- **Combine node** — ``{ "type": "combine", "operator": "UNION"|"INTERSECT"|..., "left": <node>, "right": <node> }``
  The orchestrator creates the combine step after both children complete.

The agent produces delegation plans when it has a concrete build approach
and consumes them via ``delegate_strategy_subtasks(goal, plan)``.
:py:func:`veupath_chatbot.ai.orchestration.delegation.build_delegation_plan` normalizes and validates the plan into
:py:class:`veupath_chatbot.ai.orchestration.delegation.DelegationPlan`.

SSE Event Contract
------------------

The chat stream emits these event types (see :py:mod:`veupath_chatbot.transport.http.streaming`):

- ``message_start`` — New turn; includes strategy snapshot.
- ``tool_call_start`` / ``tool_call_end`` — Main agent tool execution.
- ``subkani_task_start`` / ``subkani_tool_call_start`` / ``subkani_tool_call_end`` / ``subkani_task_end`` — Sub-kani activity.
- ``strategy_update`` — Graph changed (new step, update, delete).
- ``graph_snapshot`` — Full graph state.
- ``assistant_delta`` / ``assistant_message`` — Streaming text.
- ``optimization_progress`` — Parameter optimization updates.
- ``message_end`` — Turn complete.

.. _overview-mentions:

@-Mentions (Chat)
-----------------

Chat requests can include **mentions**: references to a strategy or an
experiment. The backend loads the referenced entity and injects a rich context
block into the prompt so the agent can reason about "this strategy" or "this
experiment". See :py:mod:`veupath_chatbot.services.chat.mention_context`:
``build_mention_context(mentions, strategy_repo)``. Mention types are
``"strategy"`` and ``"experiment"``; each mention has ``type``, ``id``, and
``displayName``.

See Also
--------

- :doc:`experiments` — Experiment Lab: modes, execution, analysis, control sets
- :doc:`agents` — PathfinderAgent (unified), SubtaskAgent
- :doc:`subkani` — Sub-kani orchestrator and scheduler
- :doc:`delegation` — Delegation plan schema and validation
- :doc:`ai_functions` — Full AI function reference
