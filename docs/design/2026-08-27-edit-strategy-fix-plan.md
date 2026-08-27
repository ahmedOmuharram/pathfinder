# The edit_strategy fix: execution plan (2026-08-27)

> Status: **PLANNED, nothing executed.** This document turns three filed
> expressions of one defect into batches an implementation agent can execute and
> a reviewer can verify. Every claim about current code was read from the
> working tree on 2026-08-27 and is cited as `path:line`; paths under
> `apps/api/src/pathfinder/` are written relative to that directory. Where a
> filed backlog item and the code disagree, section 0 names the disagreement
> rather than silently planning around it. Implementation agents are Opus; each
> batch ends with a `model=fable` reviewer rerunning the full ladders.
>
> The three filed expressions:
> `docs/knowledge/backlog/edit-strategy-drops-criteria-and-claims-preserved.md`,
> `docs/knowledge/backlog/edit-turn-rebuilds-whole-strategy-and-drops-hand-edits.md`,
> and the live run measured 2026-08-27 on conversation
> `57f3fcf1-1105-406d-a3fb-5d54dcf19f45` (recorded in section 1.3).

---

## 0. Corrections to the filed ground truth

Three things the filed items assert are wrong or incomplete in a way that would
send an agent down the wrong road. They are corrected here so no brief plans
from a stale fact.

**0.1 "The generated graph operations already exist and are unused" is wrong,
and the true statement is worse.** `edit-turn-rebuilds-whole-strategy-and-drops-hand-edits.md:46`
attributes that claim to the graph architecture review. The operation algebra is
not unused. `domain/strategy/operations/types.py:139-154` declares the
thirteen-member `GraphOperation` union; `domain/strategy/operations/apply.py`
applies it; `services/strategies/commit.py:93-168` (`apply_operations_and_commit`)
is the full commit pipeline behind it; the graph editor reaches it over HTTP at
`transport/http/routers/conversations/operations.py:22-35`; and an agent tool
`apply_operations` wraps it at `ai/tools/standalone/strategy.py:198-267`, which
is registered in the execution toolset at `ai/tools/toolsets/execution.py:107`.

What is actually true: **the operation surface is unreachable from a Lead edit
turn.** The only Lead dispatch that opens the execution toolset is
`recover_failed_steps` (`ai/lead/sub_agent_dispatch.py:244-253`), whose own
docstring restricts it to `ledger.build.needs_recovery is True`, and the Lead's
instructions restate that restriction (`ai/lead/_lead_instructions.py:30-31`).
On a *successful* strategy the Lead has exactly two strategy-changing tools:
`frame_problem` and `build_strategy`. Both are whole-strategy. So the in-place
machinery is used by the researcher's mouse and by nobody else.

**0.2 "Seed the frame with the previous turn's bound criteria" is already done,
and it is not sufficient.** `edit-strategy-drops-criteria-and-claims-preserved.md:45-46`
proposes it as the fix. `ai/lead/sub_agent_dispatch.py:69-72` already seeds
`AgentToolState.operational_spec_draft` from `state.domain.operational_spec`
when one exists. The gap is that FRAME cannot **see** what was seeded:
`pinned_frame_workspace` (`ai/agents/strategy_instructions.py:20-36`) renders
each criterion's id, first 60 characters of text, search name and open-slot
names, and **no parameter values at all**. FRAME therefore re-binds a
"preserved" criterion by calling `set_criterion` with its `text`, and
`set_criterion` re-derives every unstated parameter from that text through
`ParamIntent(text=text)` (`ai/tools/standalone/frame_spec.py:548-552`). That is
the exact mechanism behind the second measurement in that item: `Plasmodium`
narrowed to `P. falciparum 3D7` and `any_or_all` flipped from any to all,
because both were re-derived from a 60-character sentence rather than copied
from the values already bound. Seeding without rendering is a no-op the model
cannot use.

**0.3 "Old threads whose checkpoints predate the current spec schema" is not the
shape of the problem.** The house rule for a state-shape change is a checkpoint
flush, not a compatibility shim:
`docs/knowledge/decisions/no-checkpoint-truncation.md` sets `extra="forbid"` on
`StrategyDomainState` (`ai/graph/state.py:99`) and records two migrations that
truncated the checkpoint tables for exactly this reason
(`apps/api/alembic/versions/2026_08_09_0001_flush_pre_fbv_checkpoints.py`,
`2026_08_21_0001_flush_checkpoints_for_turn_state.py`). Any batch here that
changes `OperationalSpec` ships its own flush and the legacy question is closed.

The case that survives every flush, and that a shim cannot be blamed for, is
**a real strategy with no spec, produced by a path that never runs FRAME**. The
graph editor writes `conversation_strategies.strategy_ast` through
`ConversationService.apply_operation` (`transport/http/routers/conversations/operations.py:30-35`),
which is HTTP, not the graph, and touches no checkpoint. `insert_saved_strategy`
and the auto-import path do the same from inside a build. A user can therefore
own a sixteen-node strategy that `state.domain.operational_spec` has never
described. Reconstruction from the persisted AST is a permanent capability, not
a migration shim, and section 3 plans it as one.

---

## 1. Root cause

### 1.1 Stated once

An `edit_strategy` turn re-derives the whole strategy from the user's latest
sentence because nothing in the product distinguishes an edit from a fresh
build: the classification exists as a string and drives no code (`edit_strategy`
appears in exactly one non-test line of the backend,
`ai/lead/intent.py:14`, and `IntentClassification` is only ever read to render
prose at `ai/lead/lead_agent.py:101-120`); the Lead's instructions describe one
loop, FRAME to BUILD to VERIFY, with no edit branch and an explicit licence to
re-frame when "the user changes the goal" (`ai/lead/_lead_instructions.py:44-46`);
FRAME's work order is `reason` plus `state.user_prompt` and names no prior
strategy (`ai/lead/sub_agent_dispatch.py:109-114`); FRAME's own instructions are
written entirely as "turn the user's goal into a spec" and its only view of the
seeded spec renders no parameter values
(`ai/agents/frame.py:23-24`, `ai/agents/strategy_instructions.py:20-36`); the
one build path available to the Lead is `build_strategy_from_spec`, which calls
`_replace_graph_contents` to clear `graph.steps` and refill it from a freshly
converted tree (`services/strategies/spec_build.py:64-86`), whose nodes get new
ids because `operational_spec_to_step_tree` constructs every `StrategyStepNode`
without one and the field defaults to `generate_step_id`
(`domain/strategy/operational_spec.py:94-140`, `domain/strategy/ast.py:167`);
and nothing anywhere compares the spec before the turn with the spec after it,
so a dropped criterion is invisible to the build, to verification and to the
Lead's prose.

### 1.2 The three symptoms map onto that one cause

| Filed symptom | The link in the chain |
|---|---|
| Three criteria became two, reply said "preserved" | No diff exists: `derive_ledger` builds `FrameSection(spec=state.domain.operational_spec)` from the current spec only (`ai/lead/derive.py:65`, `ai/lead/ledger.py:98-113`). The Lead writes the "preserved" sentence from prose. |
| A "kept" criterion silently narrowed from Plasmodium to Pf3D7 | A kept criterion is re-bound, and re-binding re-derives params from `text` (`ai/tools/standalone/frame_spec.py:548-552`); the workspace never showed the model the values it was replacing (`ai/agents/strategy_instructions.py:20-36`). |
| An additive edit changed every WDK step id and reverted a hand edit | `_replace_graph_contents` clears the graph (`services/strategies/spec_build.py:76-79`); ids are regenerated (`domain/strategy/ast.py:167`); the Lead's `build_strategy` dispatch calls `build_strategy_from_spec` directly with no revision guard (`ai/lead/sub_agent_dispatch.py:158-203`, recorded as accepted in `docs/knowledge/decisions/build-strategy-is-not-revision-guarded.md`). |

### 1.3 The 2026-08-27 live instance, in the house format

**What I did.** On conversation `57f3fcf1-1105-406d-a3fb-5d54dcf19f45`, with an
existing sixteen-node strategy on the thread, asked to substitute the organism
to P. vivax.

**What I got.** Intent classified `edit_strategy` with the organism captured as
a hard constraint. `frame_problem` dispatched and returned
`succeeded=true`, `open_questions: 0`. The Investigation Ledger in the same
message read `frame.present=false`, `criteriaCount=0`, `boundCount=0`. The Lead
then asked the user to re-type their filters.

**Why that is wrong.** The strategy the user is being asked to re-describe is
sitting on their screen. The turn reported a successful framing over an empty
spec, which is the same screen-contradicts-itself shape as
`docs/knowledge/backlog/verification-digest-can-contradict-the-ledger.md`, and
the recovery it offers costs the researcher the whole strategy's provenance.

**Why it happens.** `frame.present` is `self.spec is not None`
(`ai/lead/ledger.py:107-109`) and the spec is `state.domain.operational_spec`
(`ai/lead/derive.py:65`). `apply_agent_state` writes the draft back only when it
carries something: `if draft.criteria or draft.dropped`
(`ai/lead/sub_agent_tools.py:181-187`). So FRAME called neither `set_criterion`
nor `drop_criterion` and still returned a `FrameResult` claiming `spec_ready`,
because `FrameResult` is three free fields with no relationship to the draft
(`ai/lead/deltas.py:12-19`) and `run_frame` accepts whatever it is handed
(`ai/lead/sub_agent_dispatch.py:126-131`).

**Which of two mechanisms produced the empty draft is not yet measured, and one
brief must settle it.** Either (a) `state.domain.operational_spec` was already
`None` on entry, because this thread's strategy was built by a path that never
framed (section 0.3), and FRAME was handed a blank draft with a work order
naming only the latest sentence; or (b) a spec existed and FRAME wrote nothing
because it read the workspace, saw nothing it could act on, and emitted a
summary. Both are fixed by this plan; the distinction decides whether E1 or E3
is the item that would have prevented this specific run, and E1's brief records
the measurement.

**Fix.** Sections 2 and 3.

**What you would get.** The organism swap patches the organism parameter on the
criteria that carry it, re-resolves only the parameters that depend on it,
leaves every other criterion's bound values byte-identical, PATCHes the affected
WDK steps in place, and reports the one thing that changed and the fifteen that
did not, from a computed diff.

---

## 2. Target design: what an `edit_strategy` turn does

### 2.1 The five stages, and what already exists for each

```
  hydrate            classify            re-bind            plan              push
+-----------+     +-----------+     +-------------+   +-------------+   +--------------+
| spec from |     | edit      |     | affected    |   | spec diff   |   | PATCH only   |
| the AST   | --> | delta:    | --> | criteria    |-->| -> Graph    |-->| changed      |
| when the  |     | keep /    |     | only, with  |   | Operation[] |   | steps; ids   |
| spec is   |     | change /  |     | dependent   |   |             |   | and hand     |
| missing   |     | drop      |     | re-resolve  |   |             |   | edits stand  |
+-----------+     +-----------+     +-------------+   +-------------+   +--------------+
   NEW (E1)          NEW (E3)          E5 uses           NEW (E4)          EXISTS
                                     param_dag                          commit.py:93
```

Only two of the five stages need new machinery in the sense of new behaviour.
The push stage is already correct and already in the tree; the plan's job is to
route the agent through it.

### 2.2 The push stage exists and is WDK-aligned already

`services/strategies/commit.py:93-168` is the pipeline the fix targets. It:

- snapshots the pre-edit tree as a deep copy so change detection is real
  (`commit.py:110-114`);
- applies every operation or rolls the whole batch back (`commit.py:118-130`);
- diffs before against after with `plan_step_pushes`
  (`commit.py:198-202`, `services/strategies/step_push_planner.py:125-170`),
  which returns `SkipAction` for an untouched step, `PatchAction` when only the
  search, parameters, display name or weight changed
  (`step_push_planner.py:85-100`), `RecreateAction` when the topology or kind
  changed, and `CreateAction` for a step with no WDK id;
- executes that plan (`services/strategies/step_wdk_push.py:425-478`), where
  `PatchAction` reaches `_update_existing_step`
  (`step_wdk_push.py:251-271`) and issues
  `PUT /users/{userId}/steps/{stepId}/search-config` through
  `StrategyAPI.update_step_search_config`
  (`integrations/veupathdb/strategy_api/steps.py:273-290`);
- invalidates only the counts of steps it actually pushed
  (`commit.py:205-209`);
- re-PUTs the strategy's step tree **only when the topology changed**
  (`commit.py:223-241`, guarded by `topology_changed`,
  `step_push_planner.py:55-58`);
- deletes orphaned WDK steps after the strategy push, never before
  (`commit.py:242-251`).

Checked against `docs/knowledge/wdk/rest/endpoint-surface.md`, the three
in-place operations WDK offers and PathFinder already wraps are:

| WDK operation | Endpoint row | PathFinder wrapper |
|---|---|---|
| Replace one step's parameters and filters | `PUT /users/{userId}/steps/{stepId}/search-config` (endpoint-surface.md:81) | `strategy_api/steps.py:273` |
| Replace the whole tree without recreating steps | `PUT /users/{userId}/strategies/{strategyId}/step-tree` (endpoint-surface.md:74) | `strategy_api/strategies.py:update_strategy` |
| Rename / save / overwrite a strategy | `PATCH /users/{userId}/strategies/{strategyId}` (endpoint-surface.md:72) | `strategy_api/strategies.py:update_strategy`, `set_saved` |
| Step metadata only (custom name, expansion) | `PATCH /users/{userId}/steps/{stepId}` (endpoint-surface.md:79) | `strategy_api/steps.py:update_step_properties` |
| Recompute a dependent vocabulary after one value changes | `POST /record-types/{rt}/searches/{name}/refreshed-dependent-params` (endpoint-surface.md:108) | `integrations/veupathdb/_searches.py:110-120` |

There is no WDK endpoint that rewrites a step's *search name* in place other
than the search-config PUT, and `_decide_leaf_or_transform` already treats a
changed `search_name` as a `PatchAction` (`step_push_planner.py:88-89`). WDK
does not offer, and this plan does not invent, an operation that changes a
step's kind without recreating it; the planner is right to call that
`RecreateAction`.

**The consequence for the design: an edit must be expressed as
`GraphOperation`s over the live graph, because that is the only input shape the
correct push pipeline accepts.** Anything that hands `build_strategy_from_spec`
a fresh tree gets new ids by construction.

### 2.3 The spec and the graph are two truths with no reconciler

`OperationalSpec` lives in the LangGraph checkpoint
(`ai/graph/state.py:103`, declared for the checkpoint allowlist at
`assistants/pathfinder_spec.py:52-67`). `StrategyAst` lives in Postgres at
`conversation_strategies.strategy_ast` and is rehydrated into the session every
turn (`services/strategies/session_factory.py:40-76`,
`domain/strategy/strategy_ast.py:14-31`). The editor writes the second and never
the first. `build_strategy_from_spec` writes the second **from** the first
(`spec_build.py:107, 118`). Nothing ever writes the first from the second, and
nothing compares them.

That is why the hand edit came back as 80: the graph said 90 and the spec said
80, the build materialised the spec, and the spec won a contest nobody had
declared. The staleness detector notices the *counts* diverging
(`domain/strategy/staleness.py:44-80`, run every turn at
`ai/lead/pre_turn.py:18-34`) and renders a warning, but it does not compare
parameters and it does not stop the rebuild.

**Design decision: for an edit turn the persisted AST is the source of truth for
what the strategy currently is, and the spec is a view derived from it.** The
spec keeps its role as the thing FRAME writes; it stops being an independent
memory of values that WDK and Postgres already hold.

### 2.4 The end-to-end turn, stage by stage

**Stage 1: hydrate.** At pre-turn (`ai/lead/pre_turn.py`, the
`PreTurnHook` already wired into the Lead node), when
`state.domain.operational_spec` is `None` or holds no criteria and the session's
graph has steps, reconstruct a spec from the AST. Section 3 specifies it.

**Stage 2: classify the edit as a delta.** The Lead already classifies intent
(`ai/lead/lead_agent.py:130-159`) and already captures typed
`explicit_constraints` (`ai/lead/intent.py:48-57`). What is missing is a typed
statement of *which criteria the request touches*. Add to the edit path an
explicit disposition per existing criterion: `kept`, `changed` (with the
parameters the request names), or `dropped` (with a reason). Nothing may be
implicitly dropped, because "implicitly" is exactly the failure.

**Stage 3: re-bind only what changed.** A `kept` criterion is copied, values
included, and never passed through `set_criterion` again. A `changed` criterion
re-runs `set_criterion` with the previously bound values as the `params` object
plus the requested overrides, which is the shape `set_criterion` already accepts
(`frame_spec.py:476-511`) and which routes into
`resolve_params_with_intent(overrides=...)`
(`services/catalog/param_dag.py:708-732`). That path is what makes an organism
swap correct rather than merely applied: `_evict_for_override`
(`param_dag.py:658-679`) unbinds a defaulted parameter that holds a value the
new override claims, the DAG re-fetches at the new context on the next pass
(`param_dag.py:730-731`), `_reconcile_dependents` hands back any dependent whose
vocabulary changed under the new parents (`frame_spec.py:411-446`), and
`validate_parameters` refreshes the dependent vocabularies against WDK before
the value is accepted (`services/catalog/param_validation.py:491-529`, reaching
`get_refreshed_dependent_params`, `integrations/veupathdb/_searches.py:110-120`).
The decision that a dependent vocabulary is only meaningful under its parents is
already recorded
(`docs/knowledge/decisions/a-dependent-vocabulary-is-read-under-its-parents.md`);
the organism swap is that decision's write path.

`update_leaf_params` is **not** the right tool for the organism swap even though
it looks like it. It merges and validates (`ai/tools/standalone/strategy.py:302-308`)
but never re-picks: a dependent value that the new organism invalidates comes
back as a WDK `ValidationError` and a `ModelRetry`, not as a re-resolution. Loud
rather than wrong, which is acceptable, but it makes the model guess the
replacement instead of reading it.

**Stage 4: plan the operations.** Diff the pre-edit spec against the post-edit
spec and emit a `GraphOperation` batch: `UpdateStepParamsOp` for a changed
criterion's step, `AddLeafOp`/`AddCombineOp`/`AddTransformOp` for a new one,
`DeleteStepOp` for a dropped one, `UpdateCombineOperatorOp` for a changed
operator. This requires a criterion-to-step-id binding, which does not exist
today; section 4's E4 brief specifies it and section 6's decision point 1 names
the two ways to carry it.

**Stage 5: push and report.** Hand the batch to `apply_operations_and_commit`
(`commit.py:93`) and report the diff, not prose. Every "preserved" sentence in
the Lead's reply is generated from the computed diff or it is not written.

### 2.5 Where the honesty gate goes

`FrameResult` is accepted unconditionally today (`ai/lead/sub_agent_dispatch.py:126-131`).
A `spec_ready` disposition over a draft with zero bound criteria is a lie the
product can detect for free. E2 makes it a `ModelRetry` inside the dispatch, and
where the retry cannot recover, a `needs_user` disposition whose summary names
the empty draft.

**This covers FRAME only.** The identical shape on the verification side, filed
as `docs/knowledge/backlog/verification-digest-can-contradict-the-ledger.md`,
is **not** closed by this plan: nothing here reconciles `digest.success` with
`ledger.build.pushed_count`, and the auto-write to cross-thread memory still
keys on that flag alone (`ai/graph/nodes.py:32-50`). E2's brief says so in its
report, that backlog item stays, and section 6's decision point 5 asks whether
to fold the general form of the check in now.

---

## 3. The strategy with no spec

### 3.1 What can be reconstructed, and from what

`StrategyAst` carries, per node: `search_name`, `parameters` as typed
`ParamValue`s, `display_name`, `operator`, `colocation_params`, the primary and
secondary input subtrees, and the step `id`
(`domain/strategy/ast.py:151-167`, `domain/strategy/strategy_ast.py:14-31`). The
outer `StrategyAst` additionally carries `record_type`, `wdk_step_ids` and
`step_counts`. The session hydrates all of it every turn
(`services/strategies/session_factory.py:40-76`).

An `OperationalSpec` needs `criteria` (id, text, search_name, role,
resolved_params) and a `structure` of leaf/combine/transform nodes
(`domain/strategy/operational_spec.py:47-81`). Every field maps:

| Spec field | Source in the AST | Fidelity |
|---|---|---|
| `Criterion.id` | the step's `id` | exact |
| `Criterion.search_name` | `StrategyStepNode.search_name` | exact |
| `Criterion.resolved_params` | `StrategyStepNode.parameters` | exact, typed, includes the researcher's hand edits |
| `Criterion.role` | derived from `infer_kind()`: no input is `seed`/`filter`, one input is `transform` | exact for transform; seed-versus-filter is positional and is decided by whether the node is the deepest leaf |
| `Criterion.text` | `display_name` | lossy: a label, not the original request sentence |
| `SpecStructure` | the tree, walked | exact, including operators |
| `OperationalSpec.record_type` | `StrategyAst.record_type` | exact |
| `Criterion.defaulted_params` | not recoverable | empty; the reconstruction says so rather than guessing |
| `Criterion.confidence`, `open_params` | not recoverable | zero / empty |

**The reconstruction is exact for everything the build consumes.** The only
lossy field is `text`, which is prose the model reads, and the only absent
fields are provenance ones that a reconstructed spec has no business asserting.
`operational_spec_to_step_tree` consumes `search_name`, `resolved_params`,
`text[:60]` and the structure (`operational_spec.py:94-140`) and nothing else,
so a reconstructed spec is buildable.

**No WDK call is required**, and the plan does not make one. The live parameter
values are already in the session graph, which is why
`get_live_strategy_state` correctly reported `min_expression_percentile: "90"`
in the filed item even while the spec said 80
(`ai/lead/live_state.py:36-66` reads `step.parameters` straight from the graph).
An optional enrichment pass could read `GET /record-types/{rt}/searches/{name}?expandParams=true`
(endpoint-surface.md:106) to label each parameter for the model's benefit, but
it is not needed for correctness and E1 does not do it.

**Asking the user is never the answer here.** The strategy is on their screen.

### 3.2 What happens to checkpoints that predate the change

Whatever `OperationalSpec` change a batch lands, that batch ships an alembic
migration that truncates the LangGraph checkpoint tables, following
`2026_08_09_0001_flush_pre_fbv_checkpoints.py` and
`2026_08_21_0001_flush_checkpoints_for_turn_state.py` and the rule in
`docs/knowledge/decisions/no-checkpoint-truncation.md`. After the flush, every
thread with a strategy is a "strategy with no spec" thread and E1's
reconstruction is what carries it. That is a feature of the sequencing: E1 lands
before any batch that changes the spec shape, so the flush is survivable when it
happens.

Any new type that reaches the checkpoint at top level must be added to
`PATHFINDER_CHECKPOINT_TYPES` (`assistants/pathfinder_spec.py:52-67`), or it is
returned as a raw payload with a logged refusal
(`docs/knowledge/decisions/the-checkpoint-allowlist-binds-at-construction.md`).
A field added to an already-declared model re-validates through that model and
needs no entry.

---

## 4. Batches and briefs

### 4.0 Standing rules restated for every brief (agents are blank slates)

An agent executes from its brief plus this section, and needs no other file.

- **TDD, no exceptions.** Write the named failing test first, watch it fail,
  then implement. Unit tests for pure logic AND integration tests where I/O is
  touched. Mock only the LLM (`PATHFINDER_CHAT_PROVIDER=mock`); WDK and
  Postgres are real in integration lanes. The api unit tier blocks sockets via
  an autouse fixture in `src/pathfinder/tests/unit/conftest.py`
  (`docs/knowledge/conventions/verification-gates.md:26-30`); a test that needs
  a database goes under `tests/integration/`.
- **Python 3.14.** `except ValueError, TypeError:` without parentheses is VALID
  (PEP 758). Do not flag it, do not "fix" it.
- **Comments.** 1 to 3 lines, simple present tense, ASCII only, no incident or
  history narration, no restating a signature. Near-zero new comments; re-read
  and delete narration after each edit.
- **No type suppressions, no `import as`** (except a genuine third-party name
  conflict), **no backwards-compat aliases or re-exports**, no
  `isinstance`/`getattr`/`dict.get` chains where a Pydantic model does the work
  (`model_validate`, `extra="ignore"`, `@field_validator`, `Discriminator`).
  PathFinder has not shipped: prefer the loud failure over a shim
  (`docs/knowledge/decisions/no-checkpoint-truncation.md`).
- **Layering.** `domain/` is pure: no I/O, no imports from services, transport
  or integrations. `uv run lint-imports` enforces six contracts and is part of
  ladder P. Pure spec logic goes in `domain/strategy/`; anything that reads WDK
  goes in `services/`.
- **Library surfaces are read, not guessed.** Before calling any pydantic-ai or
  langgraph API, open the installed source under
  `apps/api/.venv/lib/python3.14/site-packages/` and cite the line in the task
  report.
- **Machine traps.** Chat turns run in the WORKER, not the api: after any change
  to agent, tool or mock code, run
  `docker compose --env-file .env.dev up -d --build --force-recreate api worker`
  and grep the new symbol INSIDE the container before trusting a manual test;
  `up -d --build` alone can leave the old container running
  (`verification-gates.md:174-181`). Docker builds on this machine can fail on
  the credential helper; bypass with a clean empty `DOCKER_CONFIG` directory.
  Never assert timing on the first chat POST of a fresh process
  (`docs/knowledge/backlog/first-chat-post-of-a-fresh-process-pays-the-piguard-load.md`).
  The IDE's pyright may flag `assistant_core` imports the CLI run accepts; the
  gate is the CLI run from `apps/api/`.
- **Never read or print `.env*` contents.** Reference `$VAR` names only.
- **Docs in the same change.** A task that closes a backlog item deletes the
  item file AND its line in `docs/knowledge/backlog/index.md` in the same
  change; a choice with a real alternative gets a `docs/knowledge/decisions/`
  entry; ladder K after.
- **Report format.** The recap leads with remaining debt, or with the words
  "zero debt", then evidence: commands run, tail of output, baselines versus
  after.

**The gate ladders, named once** (from
`docs/knowledge/conventions/verification-gates.md`):

- **Ladder P (api)**, from `apps/api/`: `uv run ruff check src/` ;
  `uv run ruff format --check src/` ; `uv run mypy --strict src/pathfinder/` ;
  `uv run pyright src/pathfinder/` ; `uv run lint-imports` ;
  `uv run pytest src/pathfinder/tests/ -q`.
- **Ladder W (web)**, from `apps/web/`: `npx tsc --noEmit` ; `npx eslint src/` ;
  `node scripts/check-boundaries.mjs` ; `npx vitest run`.
- **Ladder K (knowledge)**, from repo root: `node scripts/check-knowledge.mjs`.
- **Ladder G (generated types)**, from repo root, only when a Pydantic model
  that reaches the wire changes: `yarn generate:types` against a running api
  container, then ladder W.

Baselines: before its first change, every task records the current pass count of
each ladder it will run. Acceptance is same-or-higher pass count, zero failures,
zero new skips. Do not hardcode counts from this document.

### 4.1 The six batches

| Batch | Goal (one sentence) | Ladders | Docker? | Size |
|---|---|---|---|---|
| E1 | A strategy with no spec gets one reconstructed from its persisted AST, exactly, with no WDK call and no question to the user | P, K | no | 1 day |
| E2 | FRAME cannot report more than it bound, and its workspace shows the values it must preserve | P, K | yes (one mock turn) | 0.5 day |
| E3 | An edit turn carries a typed per-criterion disposition, and "preserved" is computed rather than written | P, W, G, K | yes | 1.5 days |
| E4 | An edit turn's changes reach WDK as operations over the live graph, so untouched steps keep their ids and hand edits stand | P, K | yes | 2 to 3 days |
| E5 | A substitution that changes a parent parameter re-resolves the dependents it invalidates | P, K | yes | 1 day |
| E6 | The Lead routes `edit_strategy` down the edit path, the checkpoint is flushed, and the two backlog items are deleted | P, W, K | yes | 1 day |

Total: **7 to 9 engineer-days**, one agent at a time on the critical path.

Ordering: **E1 first** (E3 and E4 both consume its output, and it makes the
E6 checkpoint flush survivable). **E2 concurrently with E1** (disjoint files).
**E3 after E1.** **E4 after E3.** **E5 after E3**, concurrently with E4.
**E6 last.** Critical path: E1 -> E3 -> E4 -> E6.

**Fable review, every batch.** The reviewer gets the batch's brief and this
checklist and must be able to run it with no other context: rerun every ladder
the batch names from the stated directories and compare against the recorded
baselines (a lower count, a new skip, or a flaky rerun is a rejection); read
every file the brief names; check the CLAUDE.md absolute rules mechanically;
run the batch's named adversarial check; grep each deleted symbol's name to
prove zero references remain; confirm the backlog items the batch closes are
deleted file-and-index-line; confirm no `.env*` was read.

---

### E1. A strategy with no spec reconstructs one from its AST

**Why (2 sentences).** The 2026-08-27 run asked the user to re-type filters that
were sitting in `conversation_strategies.strategy_ast` and in the session graph,
because `state.domain.operational_spec` was `None` and nothing can build one
from what exists. Every path that produces a strategy without framing it (the
graph editor over HTTP, `insert_saved_strategy`, an auto-import, and every
thread after a checkpoint flush) produces this state permanently, so the
reconstruction is a capability and not a migration.

**Files.**
- NEW `domain/strategy/spec_hydration.py` (pure; imports only `domain/`).
- `ai/lead/pre_turn.py` (wire the hydration into `refresh_live_strategy_state`,
  which is already the `PreTurnHook` the Lead node runs).
- NEW `tests/unit/domain/strategy/test_spec_hydration.py`.
- NEW `tests/integration/ai/test_edit_turn_hydrates_spec.py`.

**The function.**

```python
# domain/strategy/spec_hydration.py
def spec_from_ast(ast: StrategyAst, *, goal: str) -> OperationalSpec:
    """Reconstruct the spec a strategy would have had.

    One criterion per non-combine node, keyed on the node's step id, holding
    the parameters the node carries. The structure mirrors the tree.
    """
```

Rules the implementation obeys, each of which has a named test:
- `Criterion.id` is the node's `id`, so a criterion and its step address the
  same thing without a side table.
- `Criterion.resolved_params` is `dict(node.parameters)`, copied, not
  re-derived. A hand-edited value survives verbatim.
- `Criterion.role` is `transform` when `node.infer_kind() == "transform"`,
  `seed` for the tree's deepest primary leaf, `filter` otherwise.
- `Criterion.text` is `node.display_name` when present, else
  `f"{node.search_name} step"`. It is a label; the docstring says so and no
  code derives a value from it.
- A combine node becomes a `StructureNode(kind="combine", operator=...)` and
  produces no criterion. Its `criterion_id` stays `None`, because
  `_count_criteria` counts any node with one set
  (`ai/tools/standalone/frame_spec.py:623-625`).
- `defaulted_params`, `open_params`, `open_slots`, `dropped` are empty and
  `confidence` is `0.0`. A reconstructed spec asserts no provenance it does not
  have.
- The function is total: it raises on nothing, because `StrategyAst`'s own
  validator already rejects duplicate ids and a missing root
  (`domain/strategy/strategy_ast.py:33-54`).

**The wiring.** In `refresh_live_strategy_state`
(`ai/lead/pre_turn.py:18-34`), after the staleness measurement, when
`working_state.domain.operational_spec` is `None` or has no criteria AND
`context.strategy_session.get_graph(None)` has steps, set
`working_state.domain.operational_spec = spec_from_ast(graph.to_strategy_ast(sync_state=...), goal=working_state.user_prompt)`.
The hook already returns a deep copy (`pre_turn.py:23`) so this mutates nothing
the checkpoint holds until the node writes its delta.

**Tests first (each RED before the change).**
- `test_reconstructed_criteria_carry_the_hand_edited_value` - build an AST whose
  leaf holds `min_expression_percentile` as the typed value for 90, reconstruct,
  assert the criterion's `resolved_params` holds 90 and not the search default.
- `test_reconstructed_spec_is_buildable` - reconstruct, call
  `operational_spec_to_step_tree`, assert it returns without raising and that
  the resulting tree's leaf `search_name`s and `parameters` equal the AST's.
- `test_criterion_ids_are_step_ids` - assert the id set equals the non-combine
  node id set.
- `test_combine_node_produces_no_criterion` - a three-leaf tree with two
  combines reconstructs three criteria, not five.
- `test_transform_role_is_derived_from_one_input` - a `GenesByOrthologs` node
  with a primary input reconstructs as `role="transform"` and as a
  `StructureNode(kind="transform")` with that input nested.
- `test_reconstruction_asserts_no_provenance` - `defaulted_params` empty,
  `confidence == 0.0`.
- `test_pre_turn_hydrates_when_the_spec_is_missing` (integration) - persist a
  conversation strategy, run the pre-turn hook with a state whose
  `operational_spec` is `None`, assert the returned state's spec has the
  criteria the AST holds. Assert with a socket-refusing double that **no WDK
  call is made** by the hydration.
- `test_pre_turn_does_not_overwrite_a_real_spec` - a state that already carries
  a spec with criteria comes back unchanged.

**Verify.** Ladder P; ladder K. Then the measurement section 1.3 leaves open:
run one real edit turn through `pathfinder.devtools.chat` in the api container
against a conversation whose strategy was built through the editor route, and
record in the task report whether the pre-hydration ledger read
`frame.present=false` (mechanism (a)) or `true` with criteria (mechanism (b)).
That measurement goes in the report, not in a new backlog file.

**Traps.** `domain/` cannot import `services/` or `integrations/`; `lint-imports`
is the gate and it will catch a convenience import of `ensure_sync_state`. The
`StrategyAst` returned by `graph.to_strategy_ast` can be `None` when the graph
has no steps, and it carries `detached_roots` for a mid-edit multi-root graph
(`strategy_ast.py:19-22`) which this function walks from `root` only, matching
what the push planner does. `pre_turn.py` runs on **every** turn, including
approval-resume turns; keep it cheap and pure.

---

### E2. FRAME cannot report more than it bound

**Why.** `run_frame` accepts whatever `FrameResult` the model emits
(`ai/lead/sub_agent_dispatch.py:126-131`), and `FrameResult` has no relationship
to the draft (`ai/lead/deltas.py:12-19`), so the 2026-08-27 run reported
`succeeded=true` and `0 open questions` while the ledger read `criteria 0`.
Separately, FRAME's only view of a seeded spec renders no parameter values
(`ai/agents/strategy_instructions.py:20-36`), which is why a "kept" criterion
gets re-derived from a 60-character label.

**Files.** `ai/lead/sub_agent_dispatch.py`, `ai/agents/strategy_instructions.py`,
`ai/lead/dispatch_messages.py`, NEW
`tests/unit/ai/lead/test_frame_result_matches_the_draft.py`,
`tests/unit/ai/agents/` (extend the pinned-instruction tests).

**Changes.**
1. In `run_frame`, after `apply_agent_state`, when the returned delta claims
   `disposition == "spec_ready"` and the draft has no bound criterion, raise
   `ModelRetry` naming the contradiction and listing the three calls that record
   work (`set_criterion`, `set_structure`, `drop_criterion`). One retry; the
   agent already has `retries=3` (`ai/agents/frame.py:153`). If the retry does
   not produce a bound criterion, return the `needs_user` result
   `frame_result_from_draft` already builds for the empty case
   (`ai/lead/dispatch_messages.py:20-27`), so the Lead is told the truth rather
   than handed a success.
2. `pinned_frame_workspace` renders each criterion's bound parameter values, in
   wire form via `to_wire` (`domain/parameters/values.py`), not only its name
   and search. Add one line to its prose: values shown here are already bound
   and are preserved unless the request changes them.

**Tests first.**
- `test_spec_ready_over_an_empty_draft_is_a_retry` - drive `run_frame` with a
  stubbed `stream_sub_agent` returning `FrameResult(disposition="spec_ready")`
  and an untouched draft; assert `ModelRetry` with the tool names in the text.
- `test_spec_ready_with_one_bound_criterion_passes` - the same with one bound
  criterion; assert it returns unchanged.
- `test_second_empty_result_becomes_needs_user` - assert the returned
  disposition is `needs_user` and the summary names the empty draft.
- `test_workspace_renders_bound_values` - a draft with
  `min_expression_percentile` bound to 90 renders "90" in the workspace string.

**Verify.** Ladder P; ladder K. Then one mock turn through
`pathfinder.devtools.chat --mock` in the api container; confirm the run
artifacts show no `spec_ready` over an empty draft.

**Traps.** `ModelRetry` raised from inside a Lead dispatch tool surfaces to the
LEAD's loop, not FRAME's, unless it is raised inside the sub-agent run. Read
`stream_sub_agent` (`ai/lead/sub_agent_stream.py`) before choosing where to
raise; if the retry must reach FRAME it belongs in the agent's output validator,
not in `run_frame`. Do not touch `apply_agent_state`'s
`if draft.criteria or draft.dropped` guard (`ai/lead/sub_agent_tools.py:186`) in
this batch; E3 owns it. This batch does **not** close
`verification-digest-can-contradict-the-ledger.md`; the report says so.

**Adversarial check for the reviewer.** Grep for any other place a sub-agent's
self-reported success is consumed without checking state, and list them in the
review. `run_verification` (`sub_agent_dispatch.py:294-322`) is the known one
and stays open.

---

### E3. An edit turn carries a typed per-criterion disposition

**Why.** Nothing distinguishes an edit from a build, so "keep the rest" is
honoured only as far as the model remembers to restate it, and the reply's
"preserved" claim is prose. A dropped criterion is invisible to build, to
verification and to the ledger.

**Files.** `domain/strategy/operational_spec.py` (new pure diff), NEW
`domain/strategy/spec_diff.py`, `ai/lead/deltas.py`,
`ai/lead/sub_agent_dispatch.py`, `ai/agents/frame.py` (instructions),
`ai/lead/ledger.py` + `ai/lead/derive.py` (surface the diff),
`ai/graph/state.py` (carry the pre-turn spec), `assistants/pathfinder_spec.py`
(checkpoint types if a new top-level type appears), NEW
`tests/unit/domain/strategy/test_spec_diff.py`, NEW
`tests/unit/ai/lead/test_edit_preservation_gate.py`,
`packages/shared-ts` regeneration if the ledger data part changes.

**Types.**

```python
# domain/strategy/spec_diff.py
class CriterionChange(CamelModel):
    criterion_id: str
    disposition: Literal["kept", "changed", "added", "dropped"]
    changed_params: dict[str, str] = Field(default_factory=dict)  # name -> new wire value
    reason: str = ""

class SpecDiff(CamelModel):
    changes: list[CriterionChange] = Field(default_factory=list)
    structure_changed: bool = False

def diff_specs(before: OperationalSpec, after: OperationalSpec) -> SpecDiff: ...
```

`diff_specs` is pure, keys on `Criterion.id`, compares `resolved_params` by
value, and reports `structure_changed` by comparing the rendered structure.

**Behaviour.**
1. `PipelineState.domain` gains `spec_before_turn: OperationalSpec | None`,
   written by the pre-turn hook (after E1's hydration) and read at turn end.
2. `FrameResult` gains `changes: list[CriterionChange]`. FRAME's instructions
   gain one edit paragraph: when the workspace is non-empty, state a disposition
   for **every** criterion already there; a criterion the request does not
   mention is `kept` and must not be re-bound.
3. In `run_frame`, when `spec_before_turn` has criteria, compute
   `diff_specs(before, after)` and reject a result that drops a criterion the
   model did not declare `dropped`, with a `ModelRetry` naming the criterion id
   and its text. This is the gate the first backlog item asks for, expressed as
   a computed check rather than a prompt.
4. `FrameSection` gains the diff so the ledger renders "kept 2, changed 1,
   dropped 0" instead of "criteria 3".
5. The Lead's instructions gain one rule: a sentence claiming anything was
   preserved is written from `ledger.frame.diff` and from nothing else.

**Tests first.**
- `test_diff_reports_a_dropped_criterion` / `..._a_changed_param` /
  `..._an_added_criterion` / `..._identical_specs_are_all_kept`.
- `test_undeclared_drop_is_a_retry` - before has three criteria, after has two,
  `changes` declares no `dropped`; assert `ModelRetry` naming the missing id.
- `test_declared_drop_passes` - the same with the drop declared.
- `test_kept_criterion_keeps_its_values` - before holds organism `Plasmodium`,
  the request touches a different criterion, after holds `Plasmodium`; a result
  where it became `Pf3D7` and was declared `kept` is a retry.
- `test_ledger_renders_the_diff` - the summary string contains the counts.
- A regression test replaying the filed measurement: three criteria (text, GO,
  expression), a request that changes only the expression dataset, assert the
  gate rejects a two-criterion result.

**Verify.** Ladder P; ladder W and ladder G **only if** the ledger data part's
schema changed (it does if `FrameSection` gains a typed field; run
`yarn generate:types` against a running api container and then ladder W); ladder
K. Add a decision doc for the "preserved is computed, never written" rule.

**Traps.** `StrategyDomainState` is `extra="forbid"` (`ai/graph/state.py:99`), so
a new field needs the migration in E6, and this batch's report must say the
flush is owed. `CriterionChange` and `SpecDiff` are nested under a declared
model only if they hang off `OperationalSpec`; if they hang off
`StrategyDomainState` directly they need entries in
`PATHFINDER_CHECKPOINT_TYPES` (`assistants/pathfinder_spec.py:52-67`). The
ledger is rendered into a `data-*` stream part; changing its shape without
regenerating `packages/shared-ts` breaks the frontend silently
(`docs/knowledge/decisions/one-way-to-generate-types.md`).

---

### E4. The edit reaches WDK as operations, not as a rebuild

**Why.** `build_strategy_from_spec` clears the graph
(`services/strategies/spec_build.py:76-79`) and every node it rebuilds gets a
fresh id (`domain/strategy/ast.py:167`), so an additive edit changed all four
WDK step ids, orphaned three server-side steps and reverted a hand edit. The
correct pipeline exists (`services/strategies/commit.py:93-168`) and takes
`GraphOperation`s; nothing converts a spec change into them.

**Files.** NEW `domain/strategy/spec_to_operations.py` (pure),
`ai/lead/sub_agent_dispatch.py` (a new Lead dispatch, `edit_strategy`),
`ai/lead/lead_agent.py` (register it), `ai/lead/_lead_instructions.py`,
NEW `tests/unit/domain/strategy/test_spec_to_operations.py`,
NEW `tests/integration/services/strategies/test_edit_preserves_step_ids.py`.

**The function.**

```python
# domain/strategy/spec_to_operations.py
def operations_for(diff: SpecDiff, *, before: OperationalSpec,
                   after: OperationalSpec) -> list[GraphOperation]:
    """The smallest batch of graph operations that turns `before` into `after`."""
```

Mapping, one rule per disposition:
- `kept` -> no operation.
- `changed`, parameters only -> `UpdateStepParamsOp(step_id=criterion.id, parameters=after_criterion.resolved_params)`.
- `changed`, search name -> `ReplaceSubtreeOp` on that step id with a one-node
  subtree carrying the new search and params, so the planner's
  `_decide_leaf_or_transform` sees a `PatchAction` for a changed search
  (`services/strategies/step_push_planner.py:88-89`) and the step id survives.
- `added` leaf under an existing combine -> `AddLeafOp` with
  `AttachIntoSlot`, or `AddCombineOp` when the addition needs a new join.
- `added` transform at the root -> `AddTransformOp(input_id=<current root>, mode="new-root")`.
- `dropped` -> `DeleteStepOp` with the resolution the structure implies
  (`COLLAPSE_COMBINE` when the parent is a combine with a surviving sibling).
- structure-only operator change -> `UpdateCombineOperatorOp`.

**The dispatch.** A new Lead tool `edit_strategy(reason)` that (1) requires a
non-empty `spec_before_turn`, (2) runs FRAME under the edit work order from E3,
(3) computes the diff, (4) computes the operations, (5) calls
`apply_operations_and_commit` (`services/strategies/commit.py:93`), and (6)
returns an `ExecuteDelta`-shaped result carrying the diff and the commit result.
It is revision-guarded: read `strategy_revision(graph.to_strategy_ast())` before
FRAME runs and refuse the commit if it changed, which is the guard
`apply_operations` already implements (`ai/tools/standalone/strategy.py:234-243`)
and which `build_strategy` deliberately lacks
(`docs/knowledge/decisions/build-strategy-is-not-revision-guarded.md`). That
decision doc is amended, not contradicted: it accepts the exposure for
"materialize my spec"; an edit is not that.

**Tests first.**
- `test_kept_criterion_emits_no_operation`.
- `test_changed_param_emits_update_step_params_on_the_same_step_id`.
- `test_added_transform_emits_add_transform_with_the_current_root_as_input`.
- `test_dropped_criterion_emits_delete_step_with_collapse`.
- `test_operations_are_empty_when_the_diff_is_empty`.
- `test_edit_preserves_step_ids` (integration, real Postgres, stubbed WDK
  recording calls): build a three-step strategy, record its `wdk_step_ids`, run
  an edit that changes one leaf's parameter, assert exactly one
  `update_step_search_config` call, zero `create_step` calls, and that every
  recorded WDK step id is unchanged. This is the direct regression for
  `edit-turn-rebuilds-whole-strategy-and-drops-hand-edits.md`.
- `test_edit_does_not_re_put_the_step_tree_when_topology_is_unchanged` - assert
  no strategy step-tree PUT, relying on `topology_changed`
  (`services/strategies/commit.py:227`).
- `test_edit_refuses_on_a_changed_revision`.

**Verify.** Ladder P; ladder K. Then a live-WDK confirmation: one real edit turn
through `pathfinder.devtools.chat` (non-mock, so `WDK_DEV_EMAIL`/
`WDK_DEV_PASSWORD` are sourced in the shell and never printed) on a real
strategy; record before-and-after WDK step ids in the task report and assert by
eye that only the edited step's id is new (or none is).

**Traps.** `apply_operations_and_commit` deep-copies the pre-edit AST precisely
so the planner can detect change (`commit.py:110-114`); the new dispatch must
not pre-mutate the graph before calling it. `push_steps_with_plan` defers
"draft" steps with open parameters (`step_wdk_push.py:340-383, 445-453`); an
edit that introduces an open slot lands locally and does not push, which is
correct and the test must expect it. `_execute_patch` skips combine steps
entirely because their params are structural (`step_wdk_push.py:260-262`). The
orphan delete runs after the strategy push, never before
(`commit.py:242-251`); do not reorder it. `DeleteStepOp`'s resolutions are a
real algebra with five members (`domain/strategy/operations/types.py:14-20`) and
`domain/strategy/operations/resolutions.py` computes which apply; use it rather
than hardcoding `COLLAPSE_COMBINE`.

---

### E5. A substitution re-resolves the dependents it invalidates

**Why.** Swapping the organism changes the parent of every dependent parameter
on that search. Copying the old dependent value forward is wrong under the new
parent, and `update_leaf_params` will merge it, hand it to WDK, and surface a
rejection rather than a replacement
(`ai/tools/standalone/strategy.py:302-314`). The correct path exists:
`resolve_params_with_intent` evicts a defaulted parameter an override claims
(`services/catalog/param_dag.py:658-679`), re-fetches at the new context
(`param_dag.py:730-731`), `set_criterion` hands back changed dependents through
`redecide` (`ai/tools/standalone/frame_spec.py:411-446, 566-570`), and
`validate_parameters` refreshes the vocabularies against WDK before accepting
(`services/catalog/param_validation.py:491-529`).

**Files.** `ai/agents/frame.py` (instructions), `ai/lead/sub_agent_dispatch.py`
(the edit work order carries the substitution), NEW
`tests/unit/services/catalog/test_substitution_re_resolves_dependents.py`,
NEW `tests/integration/ai/test_organism_swap_turn.py`.

**Behaviour.** When E3's edit work order names a `changed` criterion, it carries
the criterion's currently bound `params` object plus the requested overrides,
and FRAME's edit paragraph instructs: re-call `set_criterion` with that object;
answer every `redecide` entry from the fresh vocabulary; do not null a parameter
the previous binding held unless the request removes it.

**Tests first.**
- `test_override_evicts_a_dependent_holding_the_old_parents_value` - drive
  `resolve_params_with_intent` with a two-level DAG, override the parent, assert
  the child re-resolves rather than surviving.
- `test_set_criterion_returns_redecide_when_the_child_vocabulary_changes` -
  already partly covered by the existing dependent tests; add the substitution
  shape.
- `test_organism_swap_keeps_every_other_criterion_byte_identical` (integration,
  mock LLM, stubbed WDK): a three-criterion strategy, a swap on one, assert the
  other two criteria's `resolved_params` dictionaries are equal before and
  after.
- `test_a_dependent_that_does_not_exist_under_the_new_parent_is_reported` -
  assert the turn surfaces it as an open slot or a dropped criterion, never as a
  silent default.

**Verify.** Ladder P; ladder K. Live confirmation on PlasmoDB against a real
dependent pair (the DeRisi profileset / time-point pair named in
`docs/knowledge/decisions/a-dependent-vocabulary-is-read-under-its-parents.md`
is the known one).

**Traps.** A dependent vocabulary read with no context returns WDK's defaults,
not the parents' list; that is the whole content of the decision doc above and
it is why the read must go through `fetch_at(context)` and not a bare catalog
call. `PHYLETIC_LIST_PARAMS` and the radio-pair machinery
(`frame_spec.py:303-397`) rewrite proposals before resolution; an override that
names a derived parameter directly is a retry, not a value.

---

### E6. The Lead routes the edit, and the bundle is reconciled

**Why.** Every batch above is unreachable until the Lead calls the edit path,
and `edit_strategy` is currently a string with no consumer
(`ai/lead/intent.py:14` is its only non-test occurrence).

**Files.** `ai/lead/_lead_instructions.py`, `ai/lead/lead_agent.py`,
NEW `apps/api/alembic/versions/2026_08_XX_0001_flush_checkpoints_for_spec_diff.py`,
`docs/knowledge/backlog/index.md` (two lines deleted),
`docs/knowledge/backlog/edit-strategy-drops-criteria-and-claims-preserved.md`
(deleted), `docs/knowledge/backlog/edit-turn-rebuilds-whole-strategy-and-drops-hand-edits.md`
(deleted), `docs/knowledge/log.md`, NEW decision docs, NEW
`tests/unit/ai/lead/test_edit_routing.py`.

**Changes.**
1. The Lead's operating loop gains a branch before step 2: when the
   classification is `edit_strategy` or `extend_strategy` **and** the pinned
   spec has criteria, call `edit_strategy` and never `frame_problem` +
   `build_strategy`. The existing rule at `_lead_instructions.py:44-46` is
   rewritten: an edit is not a licence to re-frame.
2. `build_strategy` the dispatch gains the guard the standalone tool already
   has: replacing a non-empty strategy is refused with a `ModelRetry` naming
   `edit_strategy`. This closes the residual exposure
   `build-strategy-is-not-revision-guarded.md` accepted, and that decision doc
   is amended in the same change to record what changed and why the original
   acceptance no longer applies.
3. The alembic migration truncates the LangGraph checkpoint tables, following
   `2026_08_09_0001` and `2026_08_21_0001`.
4. Decision docs written: "an edit is a delta, not a rebuild"; "preserved is
   computed, never written"; "the persisted AST is the truth an edit starts
   from".

**Tests first.**
- `test_lead_tool_list_contains_edit_strategy`.
- `test_build_strategy_dispatch_refuses_a_non_empty_strategy` - assert the
  `ModelRetry` text names `edit_strategy` in snake_case, because
  `build-strategy-is-not-revision-guarded.md` records that a camelCase argument
  name in an error sent the model round a retry loop.
- An eval case promoted from each closed backlog item, per
  `verification-gates.md:52-68`: written from the cataloged failure, shown to
  fail on the pre-fix code and pass after.

**Verify.** Ladder P; ladder W; ladder K. Docker rebuild with
`--force-recreate api worker` and a grep for `edit_strategy` inside the worker
container. Then the two live confirmations, one per closed item: the "change X,
keep the rest" turn and the "add a step at the end" turn, both driven one turn
at a time through `pathfinder.devtools.chat` and both recorded in the task
report with real before-and-after values.

**Traps.** Backlog items are removed when done, not marked done, file and index
line together (`docs/knowledge/backlog/index.md:5`). A migration that truncates
checkpoints is destructive and correct; do not add a data-preserving branch.
Chat turns run in the WORKER, so a prompt change that is not in the worker
container is not deployed.

---

## 5. Explicitly out of scope

- **The verification digest's own honesty gate.**
  `docs/knowledge/backlog/verification-digest-can-contradict-the-ledger.md`
  stays open. E2 fixes the FRAME instance of that shape only; nothing here
  reconciles `digest.success` with `ledger.build.pushed_count`, and the
  cross-thread auto-write still keys on that flag (`ai/graph/nodes.py:32-50`).
- **`read_live_state` quoting stale counts.**
  `docs/knowledge/backlog/live-state-quotes-stale-ancestor-counts-after-editor-edit.md`
  stays open. It does not block this plan: `read_live_state` reads *parameters*
  straight from the graph and those are current (`ai/lead/live_state.py:44-52`);
  only its *counts* are the last persisted ones. E1's hydration reads
  parameters, not counts.
- **The graph's four representations and the 57 hand-traversal sites** from the
  graph architecture review. This plan uses the operation algebra that already
  exists; it does not unify the representations.
- **The frontend's edit affordances.** No new UI. The ledger's rendering changes
  only if E3's typed diff reaches the data part, and then only through the
  generated types.
- **`clarification-turn-forgets-the-original-request.md`.** Adjacent (a
  clarification turn also re-frames from one sentence) but a different
  classification and a different entry path.
- **Non-strategy assistants.** `site_help` runs `single_agent_graph` and has no
  strategy at all.
- **The `extend_strategy` classification.** E6 routes it down the same path
  because an addition is a delta, but no separate semantics are designed for it.

---

## 6. Decision points for the owner

**1. How a criterion addresses its step.** E1 makes `Criterion.id` the step id
for a reconstructed spec, which makes E4's mapping free. For a spec FRAME
authors from scratch, the criterion id is a model-chosen label like
`c1_protease_text` and no step exists yet.
*Option A (recommended):* after a build, rewrite each criterion's id to the step
id it produced, so the invariant "criterion id is step id" holds for every spec
that has ever been built. One assignment in `build_strategy_from_spec`, no new
field, no wire change.
*Option B:* add `step_id: str | None` to `Criterion` and `StructureNode`. More
explicit, but both types serialize into the ledger data part, so it costs a
`yarn generate:types` run and a frontend regeneration.
*Recommendation:* **A.** It carries no new state and cannot drift.

**2. Whether `edit_strategy` is a new Lead dispatch or a flag on
`frame_problem`.**
*Option A (recommended):* a separate `edit_strategy(reason)` dispatch, as E4
specifies. The precondition is checkable in code (`spec_before_turn` non-empty),
the revision guard has an obvious home, and the Lead's tool list documents the
distinction.
*Option B:* `frame_problem(reason, mode="edit")`. Fewer tools, but the guard and
the diff gate become conditionals inside one function and the Lead can pick the
wrong mode silently.
*Recommendation:* **A.**

**3. Whether E1's reconstruction should enrich `Criterion.text` from WDK.** A
reconstructed criterion's text is the step's display name. FRAME reads that text
and, in the pre-E3 world, re-derived params from it. After E3 it never does, so
the label's only job is to be readable.
*Recommendation:* **do not enrich.** It costs a WDK read per step on every
edit turn for prose. Revisit only if a measured run shows the model
misinterpreting a display name.

**4. Whether the `build_strategy` dispatch's guard (E6, change 2) is a hard
refusal or a warning.** A hard refusal amends an accepted-risk decision
(`build-strategy-is-not-revision-guarded.md`) and could block a legitimate
"start over" request.
*Recommendation:* **hard refusal, with `clear_strategy` named in the retry text
as the way to genuinely start over.** `clear_strategy` already exists and
already requires approval (`ai/tools/toolsets/execution.py:119`), so the
deliberate destructive path is the one that asks the user.

**5. Whether to fold the general "a sub-agent cannot claim more than the state
records" check in now.** E2 does it for FRAME. The verification instance is
filed and open, and both are the same assertion. Doing both at once is roughly
half a day more and produces one shared check instead of two.
*Recommendation:* **do FRAME now, verification separately**, because the
verification fix has to decide what the turn's user-visible verdict becomes when
the digest is rejected, and that is a product question this plan has not asked.

**6. Sequencing against the concurrent MCP/SDK work.** E1 through E6 touch
`ai/lead/`, `ai/agents/frame.py`, `domain/strategy/` and
`services/strategies/`. None of those is
`assistant_core/graph/single_agent.py` or `integrations/embeddings` or
`mcp/server.py`. The batches can start immediately, but E6's checkpoint flush
invalidates in-flight threads for everyone.
*Recommendation:* **land E6 in a quiet window**, and announce the flush.

---

## 7. What a reader should check first

If only one thing from this document is verified before work starts, verify
this: `grep -rn "edit_strategy" --include="*.py" apps/api/src/pathfinder | grep -v tests`
returns exactly one line, `ai/lead/intent.py:14`. Everything else here follows
from a classification that nothing reads.
