Architecture Overview
=====================

This document describes the Pathfinder API architecture: how Kani drives the
unified agent, the evaluation engine, sub-kani orchestration, delegation plans,
and the end-to-end request flow.

User-Facing Pages
-----------------

The frontend has **two user-facing pages**:

.. grid:: 2
   :gutter: 3

   .. grid-item-card:: Chat
      :class-card: sd-border-primary

      Home page (``/``). Unified agent for building/editing strategy graphs
      via natural language. Uses ``POST /api/v1/chat``. The agent decides
      per-turn whether to research, plan, or execute. Supports **@-mentions**
      of strategies and experiments (see :ref:`overview-mentions`).

   .. grid-item-card:: Workbench
      :class-card: sd-border-success

      Located at ``/workbench``. Gene set management, enrichment,
      distributions, cross-validation, and AI-powered analysis.
      Conversational WorkbenchAgent scoped to experiment context.
      See :doc:`gene_sets`.

Backend: Evaluation Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~

The **experiment endpoints** (``/api/v1/experiments/...``) are the backend
evaluation engine consumed by the workbench. They provide control-set
evaluation, classification metrics, cross-validation, and enrichment
analysis. There is no standalone ``/experiments`` page in the frontend.
See :doc:`experiments`.

High-Level Chat Flow
--------------------

.. mermaid::

   flowchart TD
       A["POST /api/v1/chat"] --> B["Chat Orchestrator"]
       B --> C["PathfinderAgent (unified)"]
       C --> D{"Single-step?"}
       D -->|yes| E["Direct tool calls"]
       D -->|no| F["delegate_strategy_subtasks"]
       F --> G["Sub-kani Orchestrator"]
       G --> H["SubtaskAgent 1"]
       G --> I["SubtaskAgent 2"]
       G --> J["SubtaskAgent N"]
       H --> K["Combine Steps"]
       I --> K
       J --> K

       style A fill:#2563eb,color:#fff
       style C fill:#7c3aed,color:#fff
       style G fill:#0891b2,color:#fff

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
- :py:class:`veupath_chatbot.ai.agents.subtask.SubtaskAgent` — Sub-agent for delegated tasks; has core tools
  (catalog, graph, execution, research) but not delegation, optimization, workbench, export, or artifacts.

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
  ``validate_graph_structure``, ``delete_step``, ``update_step``, etc.
- **Research / validation:** ``web_search``, ``literature_search``,
  ``run_control_tests``, ``optimize_search_parameters``,
  ``lookup_gene_records``, ``save_planning_artifact``.
- **Delegation:** ``delegate_strategy_subtasks`` for multi-step builds.
- **Export / results:** ``get_result_count``, ``get_download_url``,
  ``get_sample_records``, ``export_gene_set``.

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

**SubtaskAgent** — Has catalog, graph building, execution, strategy metadata,
and research tools but not delegation, optimization, workbench, export, or
artifact tools. Each sub-kani runs one delegated task.

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

The chat stream emits these event types (schemas in :py:mod:`veupath_chatbot.transport.http.schemas.sse`,
streaming logic in :py:mod:`veupath_chatbot.services.chat.streaming`):

.. list-table:: SSE Event Types
   :widths: 30 70
   :header-rows: 1

   * - Event
     - Description
   * - ``message_start``
     - New turn; includes strategy snapshot
   * - ``tool_call_start`` / ``tool_call_end``
     - Main agent tool execution
   * - ``subkani_task_start`` / ``subkani_task_end``
     - Sub-kani activity lifecycle
   * - ``strategy_update``
     - Graph changed (new step, update, delete)
   * - ``strategy_link``
     - Strategy linked to WDK (includes WDK strategy ID and URL)
   * - ``graph_snapshot``
     - Full graph state
   * - ``assistant_delta`` / ``assistant_message``
     - Streaming text
   * - ``reasoning``
     - Model reasoning/thinking blocks (Anthropic extended thinking, etc.)
   * - ``token_usage_partial``
     - Early prompt token count for UI display
   * - ``optimization_progress``
     - Parameter optimization updates
   * - ``error``
     - Stream or tool processing error
   * - ``message_end``
     - Turn complete; includes full token usage and cost estimate

.. _overview-mentions:

@-Mentions (Chat)
-----------------

Chat requests can include **mentions**: references to a strategy or an
experiment. The backend loads the referenced entity and injects a rich context
block into the prompt so the agent can reason about "this strategy" or "this
experiment". See :py:mod:`veupath_chatbot.services.chat.mention_context`:
``build_mention_context(mentions, stream_repo)``. Mention types are
``"strategy"`` and ``"experiment"``; each mention has ``type``, ``id``, and
``displayName``.

Architecture Layers
-------------------

The backend follows a layered architecture with strict dependency rules:

.. mermaid::

   flowchart TD
       T["Transport<br/><small>FastAPI routers, SSE, schemas</small>"] --> S["Services<br/><small>Business logic orchestration</small>"]
       S --> D["Domain<br/><small>Strategy AST, parameters — pure, no I/O</small>"]
       S --> I["Integrations<br/><small>WDK client, Qdrant, embeddings</small>"]
       S --> P["Persistence<br/><small>PostgreSQL, Redis</small>"]

       style T fill:#2563eb,color:#fff
       style S fill:#7c3aed,color:#fff
       style D fill:#059669,color:#fff
       style I fill:#d97706,color:#fff
       style P fill:#dc2626,color:#fff

**Key rules:**

- **Transport** depends on Services but never on Domain directly.
- **Services** orchestrate Domain + Integrations + Persistence.
- **Domain** has zero external dependencies — pure Python, no I/O.
- **Integrations** are thin HTTP/gRPC clients; business logic lives in Services.
- **Persistence** uses the repository pattern; services never write raw SQL.

Design Decisions
~~~~~~~~~~~~~~~~

.. dropdown:: Why a unified agent instead of plan-then-execute?
   :class-title: sd-font-weight-bold

   Early prototypes had separate "plan mode" and "execute mode" that the user
   toggled manually. This forced researchers to understand the system's internal
   workflow. The unified agent lets the model decide per-turn whether to
   research, plan, or execute — matching how researchers naturally describe
   goals ("find genes involved in drug resistance and intersect with high
   expression").

.. dropdown:: Why sub-kani delegation for multi-step builds?
   :class-title: sd-font-weight-bold

   A single agent building a 5-step strategy must maintain context across many
   tool calls. Sub-kanis isolate each step construction into a focused task
   with clear inputs and outputs. The orchestrator handles dependency ordering
   and combine steps, reducing the main agent's cognitive load.

.. dropdown:: Why SSE instead of WebSocket?
   :class-title: sd-font-weight-bold

   SSE is simpler (HTTP/1.1 compatible, no upgrade handshake), unidirectional
   (server -> client, which matches our stream-only chat model), and natively
   supported by browsers. The client sends new messages via POST; the server
   streams responses via SSE. This avoids the complexity of bidirectional
   WebSocket state management.

.. dropdown:: Why Redis for events?
   :class-title: sd-font-weight-bold

   Chat streams and experiment executions are long-running operations that can
   outlive individual HTTP connections. Redis Streams provide durable event logs
   that clients can reconnect to, replay from a cursor, and consume across
   process restarts. PostgreSQL handles the final persisted state; Redis handles
   the ephemeral event flow.

See Also
--------

.. grid:: 2
   :gutter: 3

   .. grid-item-card:: Evaluation Engine
      :link: experiments
      :link-type: doc

      Experiment modes, execution, analysis, and control sets.

   .. grid-item-card:: PathfinderAgent & SubtaskAgent
      :link: agents
      :link-type: doc

      Unified agent and sub-agent architecture.

   .. grid-item-card:: Sub-kani Orchestrator
      :link: subkani
      :link-type: doc

      Orchestrator and scheduler for delegated tasks.

   .. grid-item-card:: Delegation Plans
      :link: delegation
      :link-type: doc

      Plan schema and validation.

   .. grid-item-card:: AI Functions
      :link: ai_functions
      :link-type: doc

      Full AI function reference.
