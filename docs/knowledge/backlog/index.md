# Backlog

Everything known to be outstanding, ranked by what actually moves the product. Each item stands alone: a fresh session should be able to pick one up without this conversation.

Items are removed when done, not marked done. The [log](../log.md) records what left.

## UI run investigations (2026-08-17)

Bugs found by driving the real UI on PlasmoDB and VectorBase. Each records the exact steps
and values; none has a fix yet.

- [Stopping during build persists a half-built strategy; editor shows a raw 422](stop-during-build-leaves-half-persisted-strategy.md) - recordType "" and no WDK ids on disk; every count "..."; step-counts 422 MISSING_RECORD_TYPE
- [edit_strategy drops a criterion the user asked to keep and says "preserved"](edit-strategy-drops-criteria-and-claims-preserved.md) - "change X, keep the rest" re-framed to 2 of 3 criteria; the reply asserted the rest was kept
- [get_live_strategy_state quotes stale ancestor counts after an editor edit](live-state-quotes-stale-ancestor-counts-after-editor-edit.md) - UI shows 7, Lead says 15; the "live" read is the last persisted count
- ["Add a step at the end" rebuilds the whole strategy and silently reverts a hand edit](edit-turn-rebuilds-whole-strategy-and-drops-hand-edits.md) - percentile 90 went back to 80, every WDK step id changed, reply says nothing
- [Verification launches an unrequested enrichment task and its result is lost on resume](verification-durable-task-result-lost-on-resume.md) - phase card stays "started", ledger shows the previous turn's verdict, reply has no verification
- [Branching from an earlier message copies the latest strategy, not the one at that message](branch-copies-latest-strategy-not-strategy-at-branch-point.md) - transcript says 3 steps, panel shows 4
- [A branch replays the parent's message ids, so Revert in a branch 404s silently](branch-keeps-parent-message-ids-so-revert-404s.md) - fork.py mints new Message ids but leaves the chunks' ids alone; the dialog shows no error
- [Revert succeeds on the server but the client keeps the reverted turns until reload](revert-does-not-truncate-client-thread.md) - two contradictory answers on one screen
- [The agent cannot find a saved strategy by name or id, and builds the leftover criterion alone](agent-cannot-see-saved-strategy-library.md) - 187K-token frame to ask for an id; given the id, a 1-step decoy strategy is built
- [Enrichment "N genes analyzed" shows a term's background count](enrichment-genes-analyzed-shows-background-count.md) - 46-gene set reports 217 analyzed; percentInResult on the wire is result over background
- [Every scored variant fails at persist time (typed ParamValues into WDKSearchConfig) and the UI prints pydantic dumps](scored-comparison-single-mode-persists-typed-params.md) - materialization single-mode branch skips encode_params; Lead then says "no control set" falsely
- [The worker heartbeat stalls during a turn and the whole UI shows "Some services failed to start"](worker-heartbeat-starves-during-turn-and-ui-gate-goes-fatal.md) - heartbeat 153 s stale mid-frame; 30 s window; fatal gate on every page load
- [A clarification turn forgets the original request and asks for the motif the user already gave](clarification-turn-forgets-the-original-request.md) - organism silently became Aedes aegypti; RNA-Seq and GO dropped; 297K-token frame
- ["Please remember my preference" runs frame/build/verify and leaves a decoy strategy](remember-request-builds-a-strategy.md) - 182K tokens, WDK strategy 330534643, junk strategy memory; the remember tool was not called
- [Small UI defects from the run, one line each](ui-run-minor-findings.md) - lagging status labels, meaningless dots, nameless buttons, 866px collapse, workbench restore/polling, raw error strings

## Chat

- [What remains of the e2e reds is full-suite worker contention on a few feature specs](e2e-suite-residual-failures-after-auth-overhaul.md) - frame-nonconformant mocks and the rehydration 422 are fixed; auto-build, execution-phase and ai-workbench-integration pass standalone and starve only when a full parallel run holds every worker slot

- [A chat turn can run for half an hour and then error](chat-turn-hangs-for-half-an-hour.md) - the same prompt takes 12.7-29.6 s normally and 42.9 s under load, against 1039 s and 1909 s on fungidb and 939 s on tritrypdb; the turn holds its worker slot throughout, so every other conversation queues behind it

- [FRAME's tool budget does not scale with the problem](frame-budget-does-not-scale.md) - nine criteria do not fit in 60 calls, and the bound ones are discarded

- [A parameter sweep's per-variant progress collapses to one lane on the thread](sweep-progress-collapses-to-one-lane-on-the-thread.md) - every variant writes `data-task-progress` under the same `id`, so the reducer keeps one part for the whole fan-out and the bar jumps between variants
- [A resumed approval turn omits tool-input-start](resumed-approval-turn-omits-tool-input-start.md) - pydantic-ai's resume marks the id started so the adapter never backfills; the client tolerates it but PROTOCOL 6.2 describes start-first; one decision plus a conformance case

## Agents

- [Stating what you are working on builds a whole strategy, unasked, for half a dollar](a-context-statement-builds-a-strategy.md) - measured: a bare context sentence drove 26 tool calls, 231,891 tokens, $0.47 and a persisted WDK strategy on the real account; the general form of the remember-request defect


- [A search selection carries six fields nothing writes](search-selection-fields-have-no-writer.md) - `SearchOverview` keeps `decided`, `selection_status`, `rationale`, `selection_reason`, `confidence` and `param_hints`, whose only writer was an unregistered tool; two catalog tools still filter on them, so the filter is always empty

- [A numeric bound stated in the request is ignored, then reported as honoured](numeric-intent-ignored-then-reported-as-honoured.md) - the resolution half is closed; a reply can still restate a bound value with an interpretation the value does not support

- [No way for a user to authorise defaults](frame-ignores-use-defaults.md) - the slots now fill, but "pick something sensible" still has no mechanism and an assumed value is only narrated, not recorded

- [A verification digest can report success over a build that pushed nothing](verification-digest-can-contradict-the-ledger.md) - one message showed "build - failed" and "Verified end-to-end." together while the ledger read criteria 0 / pushed 0 / succeeded no; nothing checks the digest against the build

- [The services layer's purity has two exceptions](services-layer-purity-has-two-exceptions.md) - two experiment tool modules import pydantic_ai inside services, and the relocated catalog helper keeps an unreachable branch plus a tree-vocabulary filter that no-ops

- [The eval extractor doubles a turn on a legacy duplicate envelope](eval-extraction-doubles-a-turn-on-legacy-duplicate-envelopes.md) - read_turns opens a turn per user-message envelope; four legacy conversations extract a phantom turn with a doubled request

## WDK integration

Ranked by consequence, and each item states its own blast radius rather than leaving it to
be assumed.

- [219 of the 237 hidden required defaults are still unmeasured](hidden-required-default-chooses-the-science.md) - the sweep exists and runs nightly; one search whose published defaults all resolve returns zero rows, and `channel` and `dataset_url` are blocked by a visible parameter first

- [The substitution detector compares filter and input-step params as text](substitution-detector-compares-some-params-as-text.md) - a filter WDK re-serialized reads as a value WDK chose, and an input-step reads as one the caller never set

- [A strategy's record class is read off its first leaf, and WDK reads it off the root](strategy-record-class-comes-from-the-leaves.md) - the one WDK rule that no test can hold today: the graph's single record type also addresses every step's search URL, so the fix is a per-node record class

- [GenesByOrthologPattern's vocabulary fails validation, and the failure reads as "Search not found"](ortholog-pattern-vocabulary-is-unreadable-and-reported-as-not-found.md) - `WDKVocabTerm` requires a null third element and live plasmodb sends a parent term there; the refusal lists the search in its own did-you-mean, so no route reads that search's parameters


- [Thirteen shipped embedding caches are in a format the loader rejects](thirteen-shipped-embedding-caches-are-in-a-format-the-loader-rejects.md) - 7184 of 7699 shipped catalog entries have no usable row, so a fresh deployment encodes them all before readiness closes; only plasmodb carries the content-addressed shape

## Verification gates

- [The opt-in llm test tier cannot even collect](llm-test-tier-cannot-collect.md) - its conftest imports a deleted symbol and every ladder excludes the tier, so the rot is invisible; repair or delete, plus a collection-only smoke

- [The first chat POST of a fresh test process pays the PIGuard load](first-chat-post-of-a-fresh-process-pays-the-piguard-load.md) - the dispatcher awaits the injection scan before deferring, the scanner builds its onnx session on first use, and under load that beats the 5 s enqueue ceiling; the failing test floats to whichever is the process's first chat POST

- [apps/web whole-dir eslint cannot complete on this host](web-eslint-whole-dir-oom.md) - OOM at 4 GiB and at 10 GiB heaps while npx eslint src/ passes; CI runs the failing form on 7 GiB, so the step can never pass
- [The web lint job is red on a formatting check CLAUDE.md's documented commands do not run](web-lint-job-is-red-on-formatting.md) - 645 files were wrapped narrower than the `printWidth: 88` the config declares, so `lint-web` cannot pass and the write-mode pre-commit hook can bury a change

- [The API lint job is red on two checks CLAUDE.md's documented commands do not run](api-lint-job-is-red-on-alembic-and-pip-audit.md) - `ruff check .` over `alembic/`, and 44 advisories across 14 packages including the checkpoint path

- [The api file-size gate is red on two service modules](file-size-gate-is-red-on-two-service-modules.md) - `param_dag.py` at 649 lines and `step_wdk_push.py` at 416 against a 400 cap; the hook runs on any api Python change, so it fails for work touching neither file

- [Eval scoring answers "same shape or not"](eval-scoring-is-exact-match-only.md) - one wrong operator and a completely different search both report `structure` differs, so no trend can say how much worse

- [The api and the runtime package lock different `langgraph-checkpoint` versions](two-locks-resolve-langgraph-checkpoint-differently.md) - 4.0.1 against 4.2.0 under the same two pins, and the two decode checkpoints differently, so the package suite can be green on behaviour the app never runs

- [Two api integration tests fail under machine load](two-api-integration-tests-fail-under-machine-load.md) - a wall-clock bound at `assert 1.242 < 1.2` and a teardown that truncates a conversation an in-flight turn is still writing events for; both pass in a quiet session

## Initiatives

- [Execute the EDA integration plan](execute-eda-integration-plan.md) - the seven-batch plan at [eda/plan/](../eda/plan/index.md) is written; conversational analysis authoring, durable computes, the co-edited notebook tab with visualizations, and step export remain to be built

## Known and accepted

Not backlog. Recorded as decisions because they were chosen, not deferred:

- [build_strategy is not revision-guarded](../decisions/build-strategy-is-not-revision-guarded.md)
- [No faker or msw generation](../decisions/no-faker-or-msw-generation.md)
- [The nested tree stays at the wire boundary](../decisions/nested-tree-at-the-wire-boundary.md)
