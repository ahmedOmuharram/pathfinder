AI & Agent
==========

Agent construction, model catalog, and runtime configuration. Builds the
Pathfinder agent and planner with the correct LLM engine and tools.

Overview
--------

- **Agent Factory** — Build agent and planner. Select engine (OpenAI, Anthropic,
  Google), resolve model ID, apply reasoning effort. Mode-aware (execute vs plan).
- **Model Catalog** — Model metadata, provider mappings, reasoning-effort config.
  Populates the model picker; enforces sampling constraints.

Agent Factory
-------------

**Purpose:** Build the Pathfinder agent and planner with the correct engine
and model selection. Handles mode switching (execute vs plan), per-request
overrides, and reasoning effort. Resolves model ID from override, persisted
state, or server default.

**Key functions:** :py:func:`create_agent`, :py:func:`create_planner_agent`,
:py:func:`resolve_model_id`

.. automodule:: veupath_chatbot.ai.agent_factory
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

.. automodule:: veupath_chatbot.ai.model_catalog
   :members:
   :undoc-members:
   :show-inheritance:
