Strategy Services
=================

Plan normalization, validation, serialization, and WDK snapshot handling.
Bridges between the domain AST and the persistence/WDK layer.

Overview
--------

- **Plan Normalization** — Coerce parameter values, fill defaults, resolve
  vocab terms for WDK compatibility. Called before save or push.
- **Plan Validation** — Validate against WDK constraints; structured errors.
- **Serialization** — Convert between domain AST and persistence format.
- **WDK Snapshot** — Build WDK-compatible step trees from the domain plan.

Plan Normalization
------------------

**Purpose:** Normalize plans for WDK compatibility. Coerce parameter values
to the expected types, fill defaults, resolve vocabulary terms. Called before
save or push to VEuPathDB.

**Key function:** :py:func:`canonicalize_plan_parameters`

.. automodule:: veupath_chatbot.services.strategies.plan_normalize
   :members:
   :undoc-members:
   :show-inheritance:

Plan Validation
---------------

**Purpose:** Validate plans against WDK constraints. Required parameters, valid
search names, step structure. Returns structured validation errors with field paths.

**Key function:** :py:func:`validate_plan_or_raise`

.. automodule:: veupath_chatbot.services.strategies.plan_validation
   :members:
   :undoc-members:
   :show-inheritance:

WDK Bridge
----------

**Purpose:** Bridge between PathFinder strategy representation and WDK API
payloads. Translates between domain models and WDK wire format.

.. admonition:: WDK Wire Format and Parameter Coercion
   :class: note

   WDK stores multi-pick parameter values as **JSON-encoded strings** (e.g.
   ``'["Plasmodium falciparum 3D7"]'`` rather than a native array). When
   strategies are synced from WDK via :py:func:`fetch_and_convert`, the
   ``ParameterNormalizer`` preserves this wire format in the stored plan.

   The frontend step editor automatically coerces these JSON strings into
   native arrays when parameter specs load, so widgets (TreeBox, Select,
   etc.) can match values against their vocabulary options. This coercion
   runs once per editor mount via ``coerceParametersForSpecs`` in the
   ``useStepParameters`` hook.

.. automodule:: veupath_chatbot.services.strategies.wdk_bridge
   :members:
   :undoc-members:
   :show-inheritance:

Strategy Build
--------------

**Purpose:** High-level strategy build orchestration. Coordinates step
creation and graph assembly.

.. automodule:: veupath_chatbot.services.strategies.build
   :members:
   :undoc-members:
   :show-inheritance:

Step Creation
-------------

**Purpose:** Create individual strategy steps with parameter validation
and WDK integration.

.. automodule:: veupath_chatbot.services.strategies.step_creation
   :members:
   :undoc-members:
   :show-inheritance:

Auto Import
-----------

**Purpose:** Automatic import of WDK strategies into PathFinder.

.. automodule:: veupath_chatbot.services.strategies.auto_import
   :members:
   :undoc-members:
   :show-inheritance:

Auto Push
---------

**Purpose:** Best-effort auto-push: sync a local strategy back to VEuPathDB
WDK after mutations. Runs as a background task with per-strategy locking.

.. automodule:: veupath_chatbot.services.strategies.auto_push
   :members:
   :undoc-members:
   :show-inheritance:

Session Factory
---------------

**Purpose:** Create and restore strategy sessions. Loads strategy state
from the database for chat context.

.. automodule:: veupath_chatbot.services.strategies.session_factory
   :members:
   :undoc-members:
   :show-inheritance:

Step Builders
-------------

**Purpose:** Build WDK step payloads from the strategy plan AST. Creates
the correct step structure for WDK API calls.

.. automodule:: veupath_chatbot.services.strategies.step_builders
   :members:
   :undoc-members:
   :show-inheritance:

Strategy Engine
---------------

**Purpose:** Core strategy execution engine. Graph integrity checks,
step ordering, and execution helpers.

.. automodule:: veupath_chatbot.services.strategies.engine.base
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.strategies.engine.graph_integrity
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.strategies.engine.helpers
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.strategies.engine.graph_ops
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.strategies.engine.id_mapping
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.strategies.engine.step_builder
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.strategies.engine.validation
   :members:
   :undoc-members:
   :show-inheritance:
