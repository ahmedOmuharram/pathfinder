AI & Agent
==========

Agent construction, model catalog, and runtime configuration. Builds the
Pathfinder unified agent with the correct LLM engine and tools.

Overview
--------

- **Agent Factory** — Build the unified agent. Select engine (OpenAI, Anthropic,
  Google), resolve model ID, apply reasoning effort.
- **Model Catalog** — Model metadata, provider mappings, reasoning-effort config.
  Populates the model picker; enforces sampling constraints.

.. note::

   The default model is ``openai/gpt-4.1``. Override per-request via the
   ``model`` field in the chat request body, or set ``DEFAULT_MODEL_ID``
   in the environment.

Agent Factory
-------------

**Purpose:** Build the Pathfinder unified agent with the correct engine
and model selection. Handles per-request overrides and reasoning effort.
Resolves model ID from override, persisted state, or server default.

**Key functions:** :py:func:`create_agent`, :py:func:`resolve_model_id`

.. automodule:: veupath_chatbot.ai.agents.factory
   :members:
   :undoc-members:
   :show-inheritance:

Model Catalog
-------------

**Purpose:** Model metadata and provider mappings. Which models support
reasoning, sampling restrictions (e.g. o1 must use temperature=1). Used to
populate the model picker and enforce constraints.

**Key types:** :py:class:`ModelProvider`, :py:class:`ReasoningEffort`
**Key functions:** :py:func:`get_model_entry`, :py:func:`build_reasoning_hyperparams`

.. automodule:: veupath_chatbot.ai.models.catalog
   :members:
   :undoc-members:
   :show-inheritance:

Prompts
-------

**Purpose:** System prompts for the unified agent and sub-kani agents.
Prompt templates with site context, strategy state, and tool instructions.

.. automodule:: veupath_chatbot.ai.prompts.executor_prompt
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.ai.prompts.loader
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.ai.prompts.workbench_chat
   :members:
   :undoc-members:
   :show-inheritance:

Model Pricing
-------------

**Purpose:** Cost estimation utilities for LLM API calls. Calculates USD cost
per request accounting for prompt tokens, completion tokens, and cached token
discounts.

.. automodule:: veupath_chatbot.ai.models.pricing
   :members:
   :undoc-members:
   :show-inheritance:
