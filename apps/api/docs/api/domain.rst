Domain Logic
============

Strategy plan AST, operations, and validation. Pure domain logic with no
I/O or framework dependencies. Used by the agent, serialization, and tools.

Overview
--------

- **Strategy AST** — Types for plans: ``PlanStepNode``, ``StrategyAST``,
  combine operators. Recursive structure for search/transform/combine steps.
- **Strategy Operations** — Combine operators, colocation params, WDK operator mapping.
- **Strategy Validation** — Validate against WDK constraints; emit field paths.
- **Parameters** — Specs, normalization, canonicalization, vocabulary handling.

Strategy AST
------------

**Purpose:** AST types for strategy plans. ``PlanStepNode`` is recursive (search,
transform, combine). ``StrategyAST`` wraps root + metadata. Used by the agent
and serialization layer.

**Key types:** :py:class:`PlanStepNode`, :py:class:`StrategyAST`

.. automodule:: veupath_chatbot.domain.strategy.ast
   :members:
   :undoc-members:
   :show-inheritance:

Strategy Operations
-------------------

**Purpose:** Operations on the strategy AST: combine operators, colocation
parameters, WDK operator mapping. Used when building and manipulating plans.

**Key classes:** :py:class:`CombineOp`, :py:class:`ColocationParams`
**Key functions:** :py:func:`get_wdk_operator`, :py:func:`parse_op`

.. automodule:: veupath_chatbot.domain.strategy.ops
   :members:
   :undoc-members:
   :show-inheritance:

Strategy Validation
-------------------

**Purpose:** Validate plans against WDK constraints: required parameters, valid
search names, step structure. Emits ``ValidationError`` with field paths for
UI display.

**Key function:** :py:func:`validate_strategy`

.. automodule:: veupath_chatbot.domain.strategy.validate
   :members:
   :undoc-members:
   :show-inheritance:

Parameters (Domain)
-------------------

**Purpose:** Parameter specs, normalization, and validation. Vocabulary
flattening, canonicalization, and value decoding. Used by catalog and tools.

**Key functions (specs):** :py:func:`extract_param_specs`, :py:func:`adapt_param_specs`
**Key functions (normalize):** :py:class:`ParameterNormalizer`
**Key functions (canonicalize):** Value coercion for WDK wire format

.. automodule:: veupath_chatbot.domain.parameters.specs
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.domain.parameters.normalize
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.domain.parameters.canonicalize
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.domain.parameters._decode_values
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.domain.parameters._value_helpers
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.domain.parameters.vocab_utils
   :members:
   :undoc-members:
   :show-inheritance:

Strategy Tree Walkers
---------------------

**Purpose:** Shared tree traversal utilities for strategy trees. Supports both
dict-based (raw JSON) and AST-based (typed Pydantic) tree structures. Used by
validation, compilation, and analysis.

.. automodule:: veupath_chatbot.domain.strategy.tree
   :members:
   :undoc-members:
   :show-inheritance:

Strategy — Additional Modules
------------------------------

.. automodule:: veupath_chatbot.domain.strategy.compile
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.domain.strategy.explain
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.domain.strategy.metadata
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.domain.strategy.session
   :members:
   :undoc-members:
   :show-inheritance:

Research (Domain)
-----------------

**Purpose:** Citation formatting and research output processing.

.. automodule:: veupath_chatbot.domain.research.citations
   :members:
   :undoc-members:
   :show-inheritance:
