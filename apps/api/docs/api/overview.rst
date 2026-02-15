Architecture Overview
=====================

This document describes the Pathfinder API architecture: how Kani drives the
agent, the two chat modes (plan vs execute), sub-kani orchestration, delegation
plans, and the end-to-end request flow.

High-Level Flow
---------------

::

  HTTP Request
       │
       ▼
  Chat Orchestrator (start_chat_stream)
       │
       ├── mode: "plan"  ──► PathfinderPlannerAgent  ──► Planner tools (catalog, artifacts, executor handoff)
       │
       └── mode: "execute" ──► PathfinderAgent  ──► Executor tools (catalog + graph building)
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

- :py:class:`veupath_chatbot.ai.agent_runtime.PathfinderAgent` — Execute mode; builds strategies with tools.
- :py:class:`veupath_chatbot.ai.planner_runtime.PathfinderPlannerAgent` — Plan mode; explores catalog, saves artifacts,
  requests executor handoff.
- :py:class:`veupath_chatbot.ai.subtask_agent.SubtaskAgent` — Sub-agent for delegated tasks; same tools as main
  agent minus delegation.

Planning vs Execution
---------------------

**Planning mode** (``mode="plan"``)

- No strategy attached. User explores data, asks questions, refines a plan.
- Planner tools: ``list_sites``, ``search_for_searches``, ``get_search_parameters``,
  ``save_planning_artifact``, ``save_delegation_plan_draft``, ``request_executor_build``,
  ``run_control_tests``, ``optimize_search_parameters``, ``lookup_gene_records``.
- Planner saves artifacts and delegation drafts. When ready, calls
  ``request_executor_build`` to hand off to the executor.
- Plan session is persisted (plan_session_id). Messages and artifacts are
  stored per session.

**Execution mode** (``mode="execute"``)

- Strategy attached. User builds and edits the strategy graph.
- Executor tools: all catalog tools plus graph-building
  (``create_step``, ``list_current_steps``, ``build_strategy``, ``delete_step``, etc.)
  and ``delegate_strategy_subtasks``.
- For **single-step** builds, the executor calls tools directly.
- For **multi-step** builds (2+ steps, combines, transforms), the executor
  calls ``delegate_strategy_subtasks(goal, plan)``, which spawns sub-kanis.

Sub-kani Orchestration
----------------------

When the executor receives a multi-step build request, it delegates to
**sub-kanis** — smaller Kani agents that each handle one task (e.g. "find
gametocyte gene search", "create step with fold_change=2").

**Flow:**

1. Main agent calls ``delegate_strategy_subtasks(goal, plan)``.
2. Orchestrator validates and normalizes the ``plan`` into a
   :py:class:`veupath_chatbot.ai.delegation_plan.DelegationPlan` (tasks + combines + dependencies).
3. For each task node (in dependency order), spawn a :py:class:`veupath_chatbot.ai.subtask_agent.SubtaskAgent`.
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

The planner produces delegation plans when it has a concrete build approach.
The executor consumes them via ``delegate_strategy_subtasks(goal, plan)``.
:py:func:`veupath_chatbot.ai.delegation_plan.build_delegation_plan` normalizes and validates the plan into
:py:class:`veupath_chatbot.ai.delegation_plan.DelegationPlan`.

SSE Event Contract
------------------

The chat stream emits these event types (see :py:mod:`veupath_chatbot.transport.http.streaming`):

- ``message_start`` — New turn; includes strategy/plan session snapshot.
- ``tool_call_start`` / ``tool_call_end`` — Main agent tool execution.
- ``subkani_task_start`` / ``subkani_tool_call_start`` / ``subkani_tool_call_end`` / ``subkani_task_end`` — Sub-kani activity.
- ``strategy_update`` — Graph changed (new step, update, delete).
- ``graph_snapshot`` — Full graph state.
- ``assistant_delta`` / ``assistant_message`` — Streaming text.
- ``optimization_progress`` — Parameter optimization updates.
- ``message_end`` — Turn complete.

See Also
--------

- :doc:`agents` — PathfinderAgent, PathfinderPlannerAgent, SubtaskAgent
- :doc:`subkani` — Sub-kani orchestrator and scheduler
- :doc:`delegation` — Delegation plan schema and validation
- :doc:`ai_functions` — Full AI function reference by mode
