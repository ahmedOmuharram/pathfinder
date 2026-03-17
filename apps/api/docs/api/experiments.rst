Experiment Lab
==============

:bdg-primary:`Single` :bdg-warning:`Multi-Step` :bdg-info:`Import`

The **Experiment Lab** is a separate area from Chat. It lets users evaluate
search/strategy performance with positive/negative control gene sets, compute
classification and rank metrics, run cross-validation, enrichment analysis, and
step-level analysis. The web app exposes it at ``/experiments``.

.. mermaid::

   flowchart LR
       A["Create Experiment"] --> B{"Mode?"}
       B -->|single| C["Run Search"]
       B -->|multi-step| D["Build Strategy"]
       B -->|import| E["Import WDK Strategy"]
       C --> F["Evaluate Controls"]
       D --> F
       E --> F
       F --> G["Metrics<br/>P/R/F1"]
       F --> H["Cross-Validation"]
       F --> I["Enrichment"]
       F --> J["Step Analysis"]

       style A fill:#2563eb,color:#fff
       style F fill:#7c3aed,color:#fff

Experiment Modes
----------------

When creating a new experiment, the user chooses a **mode** (not a chat mode):

- **single** — One search, one set of parameters. Tune parameters, run control
  tests, optional parameter optimization and cross-validation.
- **multi-step** — Build a strategy graph (multiple searches, combines,
  transforms) in the Multi-Step Builder. Evaluate the full tree with controls;
  optional step analysis (e.g. step evaluation, operator comparison, contribution,
  parameter sensitivity).
- **import** — Import an existing VEuPathDB strategy and run the same
  evaluation and analysis as multi-step.

Execution Endpoints
-------------------

.. list-table::
   :widths: 15 35 50
   :header-rows: 1

   * - Method
     - Endpoint
     - Description
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/``
     - Create and run a single experiment (SSE)
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/batch``
     - Run across multiple organisms (SSE)
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/benchmark``
     - Run against multiple control sets (SSE)
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/seed``
     - Seed demo strategies and control sets (SSE)

Analysis Endpoints
------------------

**Cross-experiment** (not scoped to a single experiment):

.. list-table::
   :widths: 15 35 50
   :header-rows: 1

   * - Method
     - Endpoint
     - Description
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/overlap``
     - Pairwise gene set overlap (Jaccard, shared/unique genes)
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/enrichment-compare``
     - Compare enrichment results across experiments
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/ai-assist``
     - AI assistant for the experiment wizard (SSE)

**Per-experiment** (scoped to ``{experiment_id}``):

.. list-table::
   :widths: 15 40 45
   :header-rows: 1

   * - Method
     - Endpoint
     - Description
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/{id}/cross-validate``
     - Run cross-validation on an existing experiment
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/{id}/enrich``
     - Run enrichment analysis
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/{id}/re-evaluate``
     - Re-run evaluation (e.g. after changing controls)
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/{id}/custom-enrich``
     - Custom enrichment request
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/{id}/threshold-sweep``
     - Threshold sweep for a parameter
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/{id}/step-contributions``
     - Step contribution analysis (multi-step/import)
   * - :bdg-info:`GET`
     - ``/api/v1/experiments/{id}/report``
     - Get report (e.g. markdown)

CRUD and Results
----------------

.. list-table::
   :widths: 15 40 45
   :header-rows: 1

   * - Method
     - Endpoint
     - Description
   * - :bdg-info:`GET`
     - ``/api/v1/experiments/``
     - List experiments (optional site filter)
   * - :bdg-info:`GET`
     - ``/api/v1/experiments/{id}``
     - Get one experiment
   * - :bdg-warning:`PATCH`
     - ``/api/v1/experiments/{id}``
     - Update (e.g. name)
   * - :bdg-danger:`DELETE`
     - ``/api/v1/experiments/{id}``
     - Delete an experiment
   * - :bdg-info:`GET`
     - ``/api/v1/experiments/importable-strategies``
     - List strategies available for import-mode
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/create-strategy``
     - Create a strategy (for experiments)
   * - :bdg-info:`GET`
     - ``/api/v1/experiments/{id}/results/``
     - Attributes, sortable-attributes, records, distributions
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/{id}/results/refine``
     - Refine result records
   * - :bdg-info:`GET`
     - ``/api/v1/experiments/{id}/strategy``
     - Get strategy for experiment
   * - :bdg-info:`GET`
     - ``/api/v1/experiments/{id}/analyses/types``
     - Available analysis types
   * - :bdg-success:`POST`
     - ``/api/v1/experiments/{id}/analyses/run``
     - Run an analysis

Persistence
-----------

Experiments are stored in the **experiments** table (see
:py:class:`veupath_chatbot.persistence.models.ExperimentRow`): id, site_id,
name, status, data (full JSON), batch_id, benchmark_id, created_at, updated_at.
The experiment store (:py:mod:`veupath_chatbot.services.experiment.store`)
keeps an in-memory cache and persists every mutation to PostgreSQL.

Control Sets
------------

Reusable positive/negative gene sets are managed at **/api/v1/control-sets**
(CRUD). They can be referenced when creating experiments (e.g.
control_set_id). See :py:class:`veupath_chatbot.persistence.models.ControlSet`.

Experiment Streaming (CQRS)
----------------------------

**Purpose:** Background task launchers for experiment execution using a CQRS
event model. Events are persisted to Redis Streams; operations are tracked in
PostgreSQL. This is how long-running experiments (single, batch, benchmark)
are kicked off and their progress communicated to the frontend via SSE.

.. automodule:: veupath_chatbot.services.experiment.core.streaming
   :members:
   :undoc-members:
   :show-inheritance:

Service Layer
-------------

Core experiment service, orchestration, and store.

.. automodule:: veupath_chatbot.services.experiment.service
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.store
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.helpers
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment._deserialize
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.materialization
   :members:
   :undoc-members:
   :show-inheritance:

Classification
~~~~~~~~~~~~~~

**Purpose:** Gene record classification by experiment membership (TP/FP/FN/TN).
Adds ``_classification`` field to WDK records based on gene ID membership in
positive and negative control sets.

.. automodule:: veupath_chatbot.services.experiment.classification
   :members:
   :undoc-members:
   :show-inheritance:

Evaluation Service
~~~~~~~~~~~~~~~~~~

**Purpose:** Re-evaluation and threshold sweep service. Pure business logic
for recomputing experiment metrics with updated controls or parameters.

.. automodule:: veupath_chatbot.services.experiment.evaluation
   :members:
   :undoc-members:
   :show-inheritance:

Metrics and Evaluation
~~~~~~~~~~~~~~~~~~~~~~

.. admonition:: Key Metrics
   :class: tip

   .. math::

      \text{Precision} = \frac{|TP|}{|TP| + |FP|}
      \qquad
      \text{Recall} = \frac{|TP|}{|TP| + |FN|}
      \qquad
      F_1 = 2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}

   Where :math:`TP` = true positives (returned genes in positive controls),
   :math:`FP` = false positives (returned genes in negative controls),
   :math:`FN` = false negatives (positive control genes not returned).

Classification metrics, rank metrics, and statistical utilities.

.. automodule:: veupath_chatbot.services.experiment.metrics
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.rank_metrics
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.stats
   :members:
   :undoc-members:
   :show-inheritance:

Analysis Features
~~~~~~~~~~~~~~~~~

Cross-validation, enrichment, overlap, comparison, robustness, and reporting.

.. automodule:: veupath_chatbot.services.experiment.cross_validation
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.enrichment
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.custom_enrichment
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.enrichment_compare
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.overlap
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.robustness
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.report
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.tree_knobs
   :members:
   :undoc-members:
   :show-inheritance:

AI Analysis
~~~~~~~~~~~

AI-powered analysis helpers and tool definitions.

.. automodule:: veupath_chatbot.services.experiment.ai_analysis_helpers
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.ai_analysis_tools
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.assistant
   :members:
   :undoc-members:
   :show-inheritance:

AI Refinement Tools
~~~~~~~~~~~~~~~~~~~

**Purpose:** AI tools for experiment strategy refinement. Function-calling
tools decorated with ``@ai_function`` that allow the workbench agent to
add search steps, combine results with gene lists, and trigger re-evaluation.

.. automodule:: veupath_chatbot.services.experiment.ai_refinement_tools
   :members:
   :undoc-members:
   :show-inheritance:

Step Analysis
~~~~~~~~~~~~~

Multi-step strategy analysis: per-step evaluation, operator comparison,
contribution analysis, and parameter sensitivity.

.. automodule:: veupath_chatbot.services.experiment.step_analysis
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.step_analysis.orchestrator
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.step_analysis.phase_step_eval
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.step_analysis.phase_operators
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.step_analysis.phase_contribution
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.step_analysis.phase_sensitivity
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.step_analysis._evaluation
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.step_analysis._tree_utils
   :members:
   :undoc-members:
   :show-inheritance:

Types
~~~~~

Pydantic models for experiment configuration, metrics, enrichment, and results.

.. automodule:: veupath_chatbot.services.experiment.types
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.types.experiment
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.types.core
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.types.metrics
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.types.enrichment
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.types.optimization
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.types.rank
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.types.step_analysis
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.types.serialization
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.types.json_codec
   :members:
   :undoc-members:
   :show-inheritance:

Seed Data
~~~~~~~~~

Demo experiment seeding (strategies, control sets, gene lists).
See :doc:`services` for full seed module reference.
