Domain Logic
============

Strategy plan AST, operations, and validation. Pure domain logic with no
I/O or framework dependencies. Used by the planner, serialization, and tools.

Overview
--------

- **Strategy AST** — Types for plans: ``PlanStepNode``, ``StrategyPlan``,
  combine operators. Recursive structure for search/transform/combine steps.
- **Strategy Operations** — Combine, transform, path resolution on the AST.
- **Strategy Validation** — Validate against WDK constraints; emit field paths.
- **Parameters** — Specs, normalization, canonicalization, vocabulary handling.

Strategy AST
------------

**Purpose:** AST types for strategy plans. ``PlanStepNode`` is recursive (search,
transform, combine). ``StrategyPlan`` wraps root + metadata. Used by the planner
and serialization layer.

**Key types:** :py:class:`PlanStepNode`, :py:class:`StrategyPlan`

.. automodule:: veupath_chatbot.domain.strategy.ast
   :members:
   :undoc-members:
   :show-inheritance:

Strategy Operations
-------------------

**Purpose:** Operations on the strategy AST: combine steps, resolve paths,
build step trees. Used when building and manipulating plans.

**Key functions:** :py:func:`combine`, :py:func:`path_to_node`

.. automodule:: veupath_chatbot.domain.strategy.ops
   :members:
   :undoc-members:
   :show-inheritance:

Strategy Validation
-------------------

**Purpose:** Validate plans against WDK constraints: required parameters, valid
search names, step structure. Emits ``ValidationError`` with field paths for
UI display.

**Key function:** :py:func:`validate_plan`

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
