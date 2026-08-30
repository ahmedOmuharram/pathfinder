# Backlog

Everything known to be outstanding, ranked by what actually moves the product. Each item stands alone: a fresh session should be able to pick one up without this conversation.

Items are removed when done, not marked done. The [log](../log.md) records what left.

## UI run investigations (2026-08-17)

Bugs found by driving the real UI on PlasmoDB and VectorBase. Each records the exact steps
and values; none has a fix yet.

- [Stopping during build persists a half-built strategy; editor shows a raw 422](stop-during-build-leaves-half-persisted-strategy.md) - recordType "" and no WDK ids on disk; every count "..."; step-counts 422 MISSING_RECORD_TYPE
- [get_live_strategy_state quotes stale ancestor counts after an editor edit](live-state-quotes-stale-ancestor-counts-after-editor-edit.md) - UI shows 7, Lead says 15; the "live" read is the last persisted count
- [Verification launches an unrequested enrichment task and its result is lost on resume](verification-durable-task-result-lost-on-resume.md) - phase card stays "started", ledger shows the previous turn's verdict, reply has no verification
- [A durable task's completion replays the Lead node from its start](durable-resume-replays-the-lead-node.md) - measured 2026-08-30 on the febrile DESeq prompt: second analysis, three compute jobs, `create_eda_step` finds no computation, no step, no `done`; fix = durable tools become deferred tools (CallDeferred + DeferredToolResults turn), retiring `Command(resume=...)`
- [Branching from an earlier message copies the latest strategy, not the one at that message](branch-copies-latest-strategy-not-strategy-at-branch-point.md) - transcript says 3 steps, panel shows 4
- [A branch replays the parent's message ids, so Revert in a branch 404s silently](branch-keeps-parent-message-ids-so-revert-404s.md) - fork.py mints new Message ids but leaves the chunks' ids alone; the dialog shows no error
- [Revert succeeds on the server but the client keeps the reverted turns until reload](revert-does-not-truncate-client-thread.md) - two contradictory answers on one screen
- [The agent cannot find a saved strategy by name or id, and builds the leftover criterion alone](agent-cannot-see-saved-strategy-library.md) - 187K-token frame to ask for an id; given the id, a 1-step decoy strategy is built
- [Enrichment "N genes analyzed" shows a term's background count](enrichment-genes-analyzed-shows-background-count.md) - 46-gene set reports 217 analyzed; percentInResult on the wire is result over background
- [Every scored variant fails at persist time (typed ParamValues into WDKSearchConfig) and the UI prints pydantic dumps](scored-comparison-single-mode-persists-typed-params.md) - materialization single-mode branch skips encode_params; Lead then says "no control set" falsely
- [The worker heartbeat stalls during a turn and the whole UI shows "Some services failed to start"](worker-heartbeat-starves-during-turn-and-ui-gate-goes-fatal.md) - heartbeat 153 s stale mid-frame; 30 s window; fatal gate on every page load; and now a starved heartbeat past `worker_dead_heartbeat_seconds` fails the running turn, so this fix is what lets that window drop below 300 s
- [A clarification turn forgets the original request and asks for the motif the user already gave](clarification-turn-forgets-the-original-request.md) - organism silently became Aedes aegypti; RNA-Seq and GO dropped; 297K-token frame
- ["Please remember my preference" runs frame/build/verify and leaves a decoy strategy](remember-request-builds-a-strategy.md) - 182K tokens, WDK strategy 330534643, junk strategy memory; the remember tool was not called
- [Small UI defects from the run, one line each](ui-run-minor-findings.md) - lagging status labels, meaningless dots, nameless buttons, 866px collapse, workbench restore/polling, raw error strings

## Thread surgery audit (2026-08-28)

Measured on throwaway rows against the dev stack; full inventory in
`docs/design/2026-08-28-thread-surgery-audit.md`.

- [A fork of a site_help thread comes back as a pathfinder thread](fork-drops-the-assistant-id.md) - fork.py omits assistant_id, so the branch's next turn runs the wrong graph over the copied checkpoints
- [A fork's copied log rows cascade-delete with the parent's task rows](fork-log-rows-cascade-with-the-parents-task-rows.md) - task_id copied verbatim plus an ondelete CASCADE; measured 5 events to 4 when the parent's task row went
- [Revert truncates the transcript and checkpoints but not the strategy](revert-leaves-the-strategy-at-post-turn-state.md) - a marker AST survived the revert that deleted the turn that built it; the revert twin of branch-copies-latest

## Chat

- [What remains of the e2e reds is full-suite worker contention on a few feature specs](e2e-suite-residual-failures-after-auth-overhaul.md) - frame-nonconformant mocks and the rehydration 422 are fixed; auto-build, execution-phase and ai-workbench-integration pass standalone and starve only when a full parallel run holds every worker slot

- [A chat turn can run for half an hour and then error](chat-turn-hangs-for-half-an-hour.md) - the same prompt takes 12.7-29.6 s normally and 42.9 s under load, against 1039 s and 1909 s on fungidb and 939 s on tritrypdb; the turn holds its worker slot throughout, so every other conversation queues behind it

- [FRAME's tool budget does not scale with the problem](frame-budget-does-not-scale.md) - nine criteria do not fit in 60 calls, and the bound ones are discarded

- [A parameter sweep's per-variant progress collapses to one lane on the thread](sweep-progress-collapses-to-one-lane-on-the-thread.md) - every variant writes `data-task-progress` under the same `id`, so the reducer keeps one part for the whole fan-out and the bar jumps between variants
- [A resumed approval turn omits tool-input-start](resumed-approval-turn-omits-tool-input-start.md) - pydantic-ai's resume marks the id started so the adapter never backfills; the client tolerates it but PROTOCOL 6.2 describes start-first; one decision plus a conformance case

- [settled_history keeps a suspended response the next prompt trips over](settled-history-keeps-a-suspended-response.md) - the trim mirrors one of pydantic-ai's two refusal conditions; unreachable today, one guard plus a pin
- [A warm-up failure outside the caught tuples is silent](warm-up-failure-outside-caught-tuples-is-silent.md) - the spawned task dies without a done callback and readiness reports loading forever
- [The devtools summary counts no local tool calls](devtools-summary-counts-no-local-tool-calls.md) - toolcalls=0 over an event log full of calls; three review sightings

## Agents

- [Stating what you are working on builds a whole strategy, unasked, for half a dollar](a-context-statement-builds-a-strategy.md) - measured: a bare context sentence drove 26 tool calls, 231,891 tokens, $0.47 and a persisted WDK strategy on the real account; the general form of the remember-request defect


- [A search selection carries six fields nothing writes](search-selection-fields-have-no-writer.md) - `SearchOverview` keeps `decided`, `selection_status`, `rationale`, `selection_reason`, `confidence` and `param_hints`, whose only writer was an unregistered tool; two catalog tools still filter on them, so the filter is always empty

- [A numeric bound stated in the request is ignored, then reported as honoured](numeric-intent-ignored-then-reported-as-honoured.md) - the resolution half is closed; a reply can still restate a bound value with an interpretation the value does not support

- [No way for a user to authorise defaults](frame-ignores-use-defaults.md) - the slots now fill, but "pick something sensible" still has no mechanism and an assumed value is only narrated, not recorded

- [A verification digest can report success over a build that pushed nothing](verification-digest-can-contradict-the-ledger.md) - one message showed "build - failed" and "Verified end-to-end." together while the ledger read criteria 0 / pushed 0 / succeeded no; nothing checks the digest against the build


- [The Lead has no way to throw a strategy away](the-lead-cannot-start-a-strategy-over.md) - `build_strategy` refuses a thread that has one and `edit_strategy` only changes one, while `clear_strategy` is registered in the execution toolset the Lead reaches only through `recover_failed_steps`

- [The persisted strategy AST is parsed into a PersistedStrategyGraph in two places](the-persisted-strategy-ast-is-parsed-in-two-places.md) - `assistants/pathfinder_spec.py` and `jobs/runtime.py` hold the same guard-parse-fallback, and chat turns run only the second

- [The services layer's purity has two exceptions](services-layer-purity-has-two-exceptions.md) - two experiment tool modules import pydantic_ai inside services, and the relocated catalog helper keeps an unreachable branch plus a tree-vocabulary filter that no-ops

- [The eval extractor doubles a turn on a legacy duplicate envelope](eval-extraction-doubles-a-turn-on-legacy-duplicate-envelopes.md) - read_turns opens a turn per user-message envelope; four legacy conversations extract a phantom turn with a doubled request

## WDK integration

Ranked by consequence, and each item states its own blast radius rather than leaving it to
be assumed.

- [219 of the 237 hidden required defaults are still unmeasured](hidden-required-default-chooses-the-science.md) - the sweep exists and runs nightly; one search whose published defaults all resolve returns zero rows, and `channel` and `dataset_url` are blocked by a visible parameter first

- [The substitution detector compares filter and input-step params as text](substitution-detector-compares-some-params-as-text.md) - a filter WDK re-serialized reads as a value WDK chose, and an input-step reads as one the caller never set

- [A strategy's record class is read off its first leaf, and WDK reads it off the root](strategy-record-class-comes-from-the-leaves.md) - the one WDK rule that no test can hold today: the graph's single record type also addresses every step's search URL, so the fix is a per-node record class

- [GenesByOrthologPattern's vocabulary fails validation, and the failure reads as "Search not found"](ortholog-pattern-vocabulary-is-unreadable-and-reported-as-not-found.md) - `WDKVocabTerm` requires a null third element and live plasmodb sends a parent term there; the refusal lists the search in its own did-you-mean, so no route reads that search's parameters



## Verification gates


- [The opt-in llm test tier cannot even collect](llm-test-tier-cannot-collect.md) - its conftest imports a deleted symbol and every ladder excludes the tier, so the rot is invisible; repair or delete, plus a collection-only smoke

- [The first chat POST of a fresh test process pays the PIGuard load](first-chat-post-of-a-fresh-process-pays-the-piguard-load.md) - the dispatcher awaits the injection scan before deferring, the scanner builds its onnx session on first use, and under load that beats the 5 s enqueue ceiling; the failing test floats to whichever is the process's first chat POST

- [apps/web whole-dir eslint cannot complete on this host](web-eslint-whole-dir-oom.md) - OOM at 4 GiB and at 10 GiB heaps while npx eslint src/ passes; CI runs the failing form on 7 GiB, so the step can never pass
- [The web lint job is red on a formatting check CLAUDE.md's documented commands do not run](web-lint-job-is-red-on-formatting.md) - 645 files were wrapped narrower than the `printWidth: 88` the config declares, so `lint-web` cannot pass and the write-mode pre-commit hook can bury a change

- [The API lint job is red on two checks CLAUDE.md's documented commands do not run](api-lint-job-is-red-on-alembic-and-pip-audit.md) - `ruff check .` over `alembic/`, and 44 advisories across 14 packages including the checkpoint path

- [The api file-size gate is red on six modules](file-size-gate-is-red-on-six-modules.md) - `param_dag.py` 649, `frame_spec.py` 562, `mcp/server.py` 522, `strategy.py` 472, `operations/apply.py` 458 and `step_wdk_push.py` 416 against a 400 cap; the hook runs on any api Python change, so it fails for work touching none of them

- [An eval case is one prompt on a fresh thread, so no case can pin an edit turn](the-eval-corpus-cannot-express-an-edit-turn.md) - `run_one_case` mints a new conversation and drives one prompt, and both edit defects are second-turn defects

- [Eval scoring answers "same shape or not"](eval-scoring-is-exact-match-only.md) - one wrong operator and a completely different search both report `structure` differs, so no trend can say how much worse

- [The api and the runtime package lock different `langgraph-checkpoint` versions](two-locks-resolve-langgraph-checkpoint-differently.md) - 4.0.1 against 4.2.0 under the same two pins, and the two decode checkpoints differently, so the package suite can be green on behaviour the app never runs

- [Two api integration tests fail under machine load](two-api-integration-tests-fail-under-machine-load.md) - a wall-clock bound at `assert 1.242 < 1.2` and a teardown that truncates a conversation an in-flight turn is still writing events for; both pass in a quiet session

## EDA (found during batches 1-3, 2026-08-28)

- [The generic and the per-dataset EDA subset searches count different genes for the same filter](generic-and-per-dataset-eda-subset-searches-disagree.md) - 5556 through GenesByEdaSubset on a real strategy push, 5602 through the per-dataset search a day earlier, same one-filter spec; not reconciled
- [The chat SSE test helper splits frames on U+2028](sse-test-helper-splits-on-unicode-line-separator.md) - `parse_sse_body` uses `splitlines()`, and a recorded study description carries one, so a tool-output frame parses in two while the wire frame is intact
- [The Playwright no-first-nth gate is red on 16 escapes](no-first-nth-gate-is-red-on-16-escapes.md) - six older specs; the EDA specs contribute none; fix with specific locators and put the script in CI
- [generate:types in mock mode injects the dev-login route](generate-types-in-mock-mode-injects-the-dev-login-route.md) - 8 generated files differ when the api container is on the e2e overlay; the generator should refuse a spec that carries `/api/v1/dev/login`
- [The web dev container runs Turbopack despite the `--webpack` rule](web-dev-server-runs-turbopack-despite-the-webpack-rule.md) - the script, the Dockerfile and two documents disagree; measure SSE once and align them
- [The frontend weak-assertion gate is red on 106 offenders outside its baseline](weak-assertion-gate-is-red-on-106-offenders.md) - a ratchet that is red on the trunk cannot ratchet; 99 remain after the chat-path sweep; fix them or re-baseline and put the script in CI
- [The EDA permissions cache is keyed by site alone, so one account's authorization answers every later account in that process](eda-permissions-cache-is-shared-by-every-account.md) - measured `same_object=True` across the service account and the dev user; `clear_study_caches` has no production caller, and `resolve_dataset` reads the same map

## Known and accepted

Not backlog. Recorded as decisions because they were chosen, not deferred:

- [build_strategy is not revision-guarded](../decisions/build-strategy-is-not-revision-guarded.md)
- [No faker or msw generation](../decisions/no-faker-or-msw-generation.md)
- [The nested tree stays at the wire boundary](../decisions/nested-tree-at-the-wire-boundary.md)
