Chat & Orchestration
====================

Chat event handling, streaming, and orchestration of the agent flow.
Coordinates between HTTP, the agent, and the strategy store.

Overview
--------

- **Bootstrap** — Load messages, attach thinking state, set up streaming.
  Used when the chat HTTP endpoint is hit.
- **Orchestrator** — Run the agent loop: send messages, handle tool calls,
  apply graph snapshots, emit SSE events.

Chat Bootstrap
--------------

**Purpose:** Bootstrap the chat session. Load existing messages from the
strategy or plan session, attach thinking state, set up streaming. Used by
the chat HTTP endpoint before starting the stream.

**Key functions:** Session loading, message merge, thinking state init

.. automodule:: veupath_chatbot.services.chat.bootstrap
   :members:
   :undoc-members:
   :show-inheritance:

Chat Orchestrator
-----------------

**Purpose:** Orchestrate the agent loop. Send user messages to the agent,
handle tool calls (create_step, build_strategy, etc.), apply graph snapshots
from tool results, emit SSE events (message_start, tool_call_start, etc.).
Coordinates between the agent and the strategy store.

**Key functions:** Main orchestration entry point, tool result handling

.. automodule:: veupath_chatbot.services.chat.orchestrator
   :members:
   :undoc-members:
   :show-inheritance:
