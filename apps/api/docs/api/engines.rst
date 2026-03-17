LLM Engines
============

Engine implementations that adapt different LLM providers to Kani's engine
interface. Each engine handles API communication, token counting, streaming,
and provider-specific quirks.

:bdg-primary:`OpenAI` :bdg-success:`Anthropic` :bdg-info:`Google` :bdg-warning:`Ollama` :bdg-danger:`Mock`

Overview
--------

PathFinder supports multiple LLM providers through Kani engine subclasses:

- **OpenAI** -- Via Kani's built-in ``OpenAIEngine``, extended with Responses API support
- **Anthropic** -- Extended with prompt caching for 90% cost reduction on long system prompts
- **Google** -- Via Kani's built-in ``GoogleEngine``
- **Ollama** -- Local models via OpenAI-compatible API
- **Mock** -- Deterministic engine for E2E testing (keyword-matched tool calls)

Class Hierarchy
~~~~~~~~~~~~~~~

.. mermaid::

   classDiagram
       class BaseEngine {
           +predict()
           +stream()
       }
       class OpenAIEngine
       class ResponsesOpenAIEngine {
           +strips encrypted_content
       }
       class AnthropicEngine
       class CachedAnthropicEngine {
           +prompt caching
           +thinking-block fix
       }
       class MockEngine {
           +keyword matching
           +deterministic
       }

       BaseEngine <|-- OpenAIEngine
       OpenAIEngine <|-- ResponsesOpenAIEngine
       BaseEngine <|-- AnthropicEngine
       AnthropicEngine <|-- CachedAnthropicEngine
       BaseEngine <|-- MockEngine

Design Decisions
~~~~~~~~~~~~~~~~

.. dropdown:: Why custom engine subclasses?
   :animate: fade-in

   Each LLM provider has quirks that require engine-level fixes:

   - OpenAI's Responses API doesn't accept ``encrypted_content`` for non-reasoning
     models -- ``ResponsesOpenAIEngine`` strips it
   - Anthropic's API returns bare thinking blocks that fail Pydantic validation --
     ``CachedAnthropicEngine`` patches the response
   - Prompt caching (Anthropic) can reduce costs by 90% for repeated system prompts --
     implemented at the engine level, transparent to agents

.. dropdown:: Mock engine for E2E testing
   :animate: fade-in

   The mock engine returns predetermined tool calls based on keyword matching in the
   user's message. Everything downstream (WDK API calls, database mutations, gene set
   operations, auto-build) runs against real services. This catches integration bugs
   that pure unit tests miss.

OpenAI Responses Engine
-----------------------

**Purpose:** OpenAI engine using the Responses API. Strips
``reasoning.encrypted_content`` from non-reasoning models to prevent 400 errors.

.. automodule:: veupath_chatbot.ai.engines.responses_openai
   :members:
   :undoc-members:
   :show-inheritance:

Anthropic Cached Engine
-----------------------

**Purpose:** Anthropic engine with prompt caching and thinking-block fixes.
Adds cache control markers to system messages, reducing cost by up to 90% on
repeated conversations. Also fixes Pydantic validation errors for bare
thinking-block responses.

.. automodule:: veupath_chatbot.ai.engines.cached_anthropic
   :members:
   :undoc-members:
   :show-inheritance:

Mock Engine (E2E Testing)
-------------------------

**Purpose:** Deterministic mock LLM engine for E2E testing. Returns
predetermined tool calls based on keyword matching in the user's message.
All downstream services (WDK, database, gene sets) run real -- only the LLM
call is mocked.

**Design:** The mock engine enables testing the full application stack (HTTP ->
services -> integrations -> persistence) without LLM API costs or
non-determinism. Test scenarios define expected tool call sequences that the
mock replays in order.

.. automodule:: veupath_chatbot.ai.engines.mock
   :members:
   :undoc-members:
   :show-inheritance:
