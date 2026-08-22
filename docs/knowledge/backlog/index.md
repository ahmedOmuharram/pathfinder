# Backlog

Everything known to be outstanding, ranked by what actually moves the product. Each item stands alone: a fresh session should be able to pick one up without this conversation.

Items are removed when done, not marked done. The [log](../log.md) records what left.

## UI run investigations (2026-08-17)

Bugs found by driving the real UI on PlasmoDB and VectorBase. Each records the exact steps
and values; none has a fix yet.

- [Stopping during build persists a half-built strategy; editor shows a raw 422](stop-during-build-leaves-half-persisted-strategy.md) - recordType "" and no WDK ids on disk; every count "..."; step-counts 422 MISSING_RECORD_TYPE
- [edit_strategy drops a criterion the user asked to keep and says "preserved"](edit-strategy-drops-criteria-and-claims-preserved.md) - "change X, keep the rest" re-framed to 2 of 3 criteria; the reply asserted the rest was kept
- [get_live_strategy_state quotes stale ancestor counts after an editor edit](live-state-quotes-stale-ancestor-counts-after-editor-edit.md) - UI shows 7, Lead says 15; the "live" read is the last persisted count
- [A regenerated turn replays the user message under its old id and the conversation can never be opened again](duplicate-user-message-id-crashes-conversation.md) - assistant-ui MessageRepository throws on the duplicate; whole chat view is an error page
- ["Add a step at the end" rebuilds the whole strategy and silently reverts a hand edit](edit-turn-rebuilds-whole-strategy-and-drops-hand-edits.md) - percentile 90 went back to 80, every WDK step id changed, reply says nothing
- [Verification launches an unrequested enrichment task and its result is lost on resume](verification-durable-task-result-lost-on-resume.md) - phase card stays "started", ledger shows the previous turn's verdict, reply has no verification
- [Branching from an earlier message copies the latest strategy, not the one at that message](branch-copies-latest-strategy-not-strategy-at-branch-point.md) - transcript says 3 steps, panel shows 4
- [A branch replays the parent's message ids, so Revert in a branch 404s silently](branch-keeps-parent-message-ids-so-revert-404s.md) - fork.py mints new Message ids but leaves the chunks' ids alone; the dialog shows no error
- [Revert succeeds on the server but the client keeps the reverted turns until reload](revert-does-not-truncate-client-thread.md) - two contradictory answers on one screen
- [The agent cannot find a saved strategy by name or id, and builds the leftover criterion alone](agent-cannot-see-saved-strategy-library.md) - 187K-token frame to ask for an id; given the id, a 1-step decoy strategy is built
- [Enrichment "N genes analyzed" shows a term's background count](enrichment-genes-analyzed-shows-background-count.md) - 46-gene set reports 217 analyzed; percentInResult on the wire is result over background
- [Every scored variant fails at persist time (typed ParamValues into WDKSearchConfig) and the UI prints pydantic dumps](scored-comparison-single-mode-persists-typed-params.md) - materialization single-mode branch skips encode_params; Lead then says "no control set" falsely
- [One failed tool call leaves an output-error part the request parser refuses, and the conversation can never send again](output-error-tool-part-bricks-conversation-on-resend.md) - differential_sides max 2 fails a 3-way compare; resultProviderMetadata is not accepted by pydantic-ai's ToolOutputErrorPart
- [The worker heartbeat stalls during a turn and the whole UI shows "Some services failed to start"](worker-heartbeat-starves-during-turn-and-ui-gate-goes-fatal.md) - heartbeat 153 s stale mid-frame; 30 s window; fatal gate on every page load
- [A clarification turn forgets the original request and asks for the motif the user already gave](clarification-turn-forgets-the-original-request.md) - organism silently became Aedes aegypti; RNA-Seq and GO dropped; 297K-token frame
- ["Please remember my preference" runs frame/build/verify and leaves a decoy strategy](remember-request-builds-a-strategy.md) - 182K tokens, WDK strategy 330534643, junk strategy memory; the remember tool was not called
- [Small UI defects from the run, one line each](ui-run-minor-findings.md) - lagging status labels, meaningless dots, nameless buttons, 866px collapse, workbench restore/polling, raw error strings

## Chat

- [10 e2e specs still fail, all deep in composite flows](e2e-suite-residual-failures-after-auth-overhaul.md) - 120 passed / 10 failed / 0 flaky; the feature project is fully green; what remains: two real accessibility findings, one shared rail-strategy-panel assertion across five journeys, three tail-of-run flakes

- [A failed turn shows "Response failed" while it streams, and nothing at all after a reload](failed-turn-shows-no-error-after-reload.md) - neither reducer turns the `error` chunk into a part; the nine-chunk log reduces to two parts on both sides
- [FRAME's tool budget does not scale with the problem](frame-budget-does-not-scale.md) - nine criteria do not fit in 60 calls, and the bound ones are discarded

## Agents

- [A numeric bound stated in the request is ignored, then reported as honoured](numeric-intent-ignored-then-reported-as-honoured.md) - the resolution half is closed; a reply can still restate a bound value with an interpretation the value does not support

- [No way for a user to authorise defaults](frame-ignores-use-defaults.md) - the slots now fill, but "pick something sensible" still has no mechanism and an assumed value is only narrated, not recorded

- [A verification digest can report success over a build that pushed nothing](verification-digest-can-contradict-the-ledger.md) - one message showed "build - failed" and "Verified end-to-end." together while the ledger read criteria 0 / pushed 0 / succeeded no; nothing checks the digest against the build

- [The tool-repetition guard is registered on no agent](repetition-guard-runs-on-no-agent.md) - `Hooks(` appears nowhere, so the third identical read-only call is never blocked; re-wire it or delete it

## WDK integration

Ranked by consequence, and each item states its own blast radius rather than leaving it to
be assumed.

- [Whether the other 181 hidden required defaults return rows is unmeasured](hidden-required-default-chooses-the-science.md) - the one default known to return nothing is no longer filled; the rest are filled on trust, and only a per-search live run can clear them

- [The substitution detector compares filter and input-step params as text](substitution-detector-compares-some-params-as-text.md) - a filter WDK re-serialized reads as a value WDK chose, and an input-step reads as one the caller never set

- [32 of the 83 WDK rules have no test; every one of them is HARD or CONTRACT](wdk-rules-are-unenforced.md) - last in this section because it is the missing safety net under the others rather than a live hazard: the SILENT class, where WDK answers 200 and the science is wrong, is closed

## Known and accepted

Not backlog. Recorded as decisions because they were chosen, not deferred:

- [build_strategy is not revision-guarded](../decisions/build-strategy-is-not-revision-guarded.md)
- [No faker or msw generation](../decisions/no-faker-or-msw-generation.md)
- [The nested tree stays at the wire boundary](../decisions/nested-tree-at-the-wire-boundary.md)
