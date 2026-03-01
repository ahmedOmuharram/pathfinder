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
