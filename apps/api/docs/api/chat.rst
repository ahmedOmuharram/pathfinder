Chat & Orchestration
====================

Chat event handling, streaming, and orchestration of the agent flow.
Coordinates between HTTP, the agent, and the strategy store.

.. mermaid::

   sequenceDiagram
       participant Client
       participant Router
       participant Orchestrator
       participant Agent
       participant WDK

       Client->>Router: POST /api/v1/chat
       Router->>Orchestrator: start_chat_stream()
       Orchestrator->>Agent: create PathfinderAgent
       loop Streaming
           Agent->>Agent: tool call (e.g. create_step)
           Agent->>WDK: WDK API call
           WDK-->>Agent: result
           Agent-->>Orchestrator: SSE event
           Orchestrator-->>Client: SSE: tool_call_start/end
       end
       Agent-->>Orchestrator: final message
       Orchestrator-->>Client: SSE: message_end

Overview
--------

- **Events** — Chat event type definitions
- **Orchestrator** — Run the agent loop, emit SSE events
- **Streaming** — Stream processing and event handling
- **Mention Context** — @mention context injection
- **Utils** — Shared chat utilities

Chat Events
-----------

**Purpose:** Chat event type definitions for the event bus.

.. automodule:: veupath_chatbot.services.chat.events
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

Chat Streaming
--------------

**Purpose:** Stream processing for the chat agent. Handles SSE event
formatting and stream lifecycle management.

.. automodule:: veupath_chatbot.services.chat.streaming
   :members:
   :undoc-members:
   :show-inheritance:

Mention Context
---------------

**Purpose:** Build rich context from @-mentions (strategies and experiments).
Loads referenced entities and formats them for the agent's system prompt.

.. automodule:: veupath_chatbot.services.chat.mention_context
   :members:
   :undoc-members:
   :show-inheritance:

Chat Utils
----------

**Purpose:** Shared utilities for chat processing: node selection parsing,
message formatting, and stream helpers.

.. automodule:: veupath_chatbot.services.chat.utils
   :members:
   :undoc-members:
   :show-inheritance:
