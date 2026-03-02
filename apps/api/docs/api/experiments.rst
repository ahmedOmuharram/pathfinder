Experiment Lab
==============

The **Experiment Lab** is a separate area from Chat. It lets users evaluate
search/strategy performance with positive/negative control gene sets, compute
classification and rank metrics, run cross-validation, enrichment analysis, and
step-level analysis. The web app exposes it at ``/experiments``.

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

- **POST /api/v1/experiments/** — Create and run a single experiment. Request
  body matches :class:`ExperimentConfig` (site_id, record_type, mode,
  search_name/parameters or step_tree/source_strategy_id, controls, optional
  optimization, cross-validation, enrichment, step analysis). Response is SSE
  (experiment_progress, experiment_complete, experiment_error, experiment_end).

- **POST /api/v1/experiments/batch** — Run the same search across multiple
  organisms (batch). Each target has its own positive/negative controls. SSE
  stream.

- **POST /api/v1/experiments/benchmark** — Run the same strategy against
  multiple control sets in parallel. One experiment per control set; one can be
  marked primary. SSE stream.

- **POST /api/v1/experiments/seed** — Seed demo strategies and control sets
  across VEuPathDB sites (e.g. for onboarding). SSE stream; requires auth.

Analysis Endpoints
------------------

Non-parametric (must be registered before ``/{experiment_id}``):

- **POST /api/v1/experiments/overlap** — Pairwise gene set overlap between
  experiments (Jaccard, shared/unique genes).

- **POST /api/v1/experiments/enrichment-compare** — Compare enrichment results
  across experiments.

- **POST /api/v1/experiments/ai-assist** — AI assistant for the experiment
  wizard. Streams a response with tool-use (web/literature search, catalog,
  gene lookup) to help with the current wizard step. Request: site_id, step,
  message, context, history, optional model.

Parametric (per experiment):

- **POST /api/v1/experiments/{experiment_id}/cross-validate** — Run
  cross-validation on an existing experiment.

- **POST /api/v1/experiments/{experiment_id}/enrich** — Run enrichment
  analysis.

- **POST /api/v1/experiments/{experiment_id}/re-evaluate** — Re-run
  evaluation (e.g. after changing controls).

- **POST /api/v1/experiments/{experiment_id}/custom-enrich** — Custom
  enrichment request.

- **POST /api/v1/experiments/{experiment_id}/threshold-sweep** — Threshold
  sweep for a parameter.

- **POST /api/v1/experiments/{experiment_id}/step-contributions** — Step
  contribution analysis (multi-step/import).

- **GET /api/v1/experiments/{experiment_id}/report** — Get report (e.g.
  markdown).

CRUD and Results
----------------

- **GET /api/v1/experiments/** — List experiments (optional site filter).
- **GET /api/v1/experiments/{experiment_id}** — Get one experiment.
- **PATCH /api/v1/experiments/{experiment_id}** — Update (e.g. name).
- **DELETE /api/v1/experiments/{experiment_id}** — Delete.
- **GET /api/v1/experiments/importable-strategies** — List strategies that can
  be imported for import-mode experiments.
- **POST /api/v1/experiments/create-strategy** — Create a strategy (for
  experiments).
- **GET /api/v1/experiments/{experiment_id}/results/** — Attributes,
  sortable-attributes, records, distributions; **POST .../refine**.
- **GET /api/v1/experiments/{experiment_id}/strategy** — Get strategy for
  experiment.
- **GET /api/v1/experiments/{experiment_id}/analyses/types** — Available
  analysis types; **POST .../analyses/run** to run.

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

Metrics and Evaluation
~~~~~~~~~~~~~~~~~~~~~~

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

.. automodule:: veupath_chatbot.services.experiment.export
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

Seed Data
~~~~~~~~~

Demo experiment seeding (strategies, control sets, gene lists).

.. automodule:: veupath_chatbot.services.experiment.seed
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.seed.definitions
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.seed.gene_lists
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: veupath_chatbot.services.experiment.seed.runner
   :members:
   :undoc-members:
   :show-inheritance:
