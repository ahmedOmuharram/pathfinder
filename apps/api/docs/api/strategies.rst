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

**Key function:** :py:func:`normalize_plan`

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

Serialization
-------------

**Purpose:** Convert between domain AST and persistence format. Plan to/from
JSON, strategy snapshots for undo and restore.

**Key functions:** Plan serialization, snapshot build/restore

.. automodule:: veupath_chatbot.services.strategies.serialization
   :members:
   :undoc-members:
   :show-inheritance:

WDK Snapshot
------------

**Purpose:** Build WDK-compatible step trees and strategy payloads from the
domain plan. Used when pushing to VEuPathDB or creating strategies.

**Key functions:** ``_build_snapshot_from_wdk``, ``_build_node_from_wdk``

.. automodule:: veupath_chatbot.services.strategies.wdk_snapshot
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

WDK Counts
----------

**Purpose:** Fetch step result counts from WDK. Used to populate the
strategy graph UI with result counts per step.

.. automodule:: veupath_chatbot.services.strategies.wdk_counts
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
