---
type: Backlog Item
title: What remains of the e2e suite's reds is full-suite worker contention on a handful of feature specs
description: Every previously recorded failure population is resolved with a measured cause. Run 23's ten (assertion ceilings inside the 12.7-42.9 s build-turn band; five accessibility nodes) are fixed. The next full run's fourteen decomposed into: five route-mocked specs sending protocol-nonconformant SSE (no id line; fixed via a shared conformant fixture, plus parameter-sweep's pre-v6 dialect modernized), one real product bug (a rehydrated thread's turn facts and stream part metadata 422 on resend; fixed in ChatRequestBody, protocol 1.2.2), and the rest passing standalone. What remains open: auto-build (4 tests), execution-phase and ai-workbench-integration fail only under a full parallel run, when every worker slot is busy and their 15-20 s data-part waits starve. Related items cover the first-scan cost and the fungidb hang; this one is the ceiling-vs-contention question for feature specs, whose fix is either serializing turn-driving feature specs like the journeys or budgeting their waits against the measured contended band.
tags: [investigation, e2e, playwright, tests]
generated: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
status: stable
---

# Investigation (e2e stack, 2026-08-23)

**What I did.** Pulled every failing spec's *first-attempt* error out of the run-23
traces (`test.trace` inside each `trace.zip`) rather than reading the retries,
then measured what the assertions were actually waiting on: the duration of each
`chat_turn` job, from the worker's own
`procrastinate.worker` "ended with status: Success, lasted N s" lines.

**What I got.** The first-attempt errors did not match the recorded grouping. The
build turn, driven by the same mock prompt on every site, measures:

| site | build turn |
|---|---|
| tritrypdb | 12.665 s |
| cryptodb | 15.112 s |
| plasmodb | 15.758 s, 29.614 s |
| two turns at once | up to 42.921 s |

Against that, `expectRailPanel` allowed 30 000 ms, `expectAssistantMessage`
30 000 ms and `expectIdle` 60 000 ms. At the moment of every rail-panel timeout
the page showed `"Framing the strategy..."`, a live Stop button and ledger
`pushed=0`: the turn was still running, not stuck.

**Why that is wrong.** A gate that is a coin flip gates nothing. It also sent two
sessions chasing a right-rail wiring defect that does not exist, and it hid the
two accessibility findings and the hanging-turn bug underneath it.

**Why it happens.** The rail panel renders on the `data-graph-snapshot` chunk,
which `useChatRuntime` receives when the build turn completes, so the assertion's
bound is the turn's own duration plus the time it waits for a free worker slot
(measured at about 18 s). A 30 s ceiling sits inside that band. The same is true
of the other two waits, which is why the failures looked like unrelated
assertions across different journeys.

**Fix.** Each wait now carries the budget of the thing it waits on, and a test
that waits on a build turn extends its own timeout the way the enrichment helper
does, so no project timeout moved:

- `e2e/pages/graph.page.ts` - one `BUILD_TURN_BUDGET_MS`, granted once per test.
  Per-site budgets were tried and dropped: cryptodb is faster than plasmodb, so
  a per-site table would encode a split the measurements do not show.
- `e2e/pages/chat.page.ts` - `expectAssistantMessage` and `expectIdle` raised to
  the same band.
- `e2e/journey/plasmodium-drug-targets.spec.ts` - six turns do not fit the
  journey project's own budget; the test extends it.
- `e2e/journey/full-researcher-lifecycle.spec.ts` - the spec asserted a
  site-scoped sidebar after navigating to `/`, which resolves to the portal,
  where its PlasmoDB conversations correctly do not appear.

**What you would get.** Every journey that builds a strategy passes on its own
merits, and a red one means the product is broken.

# What remains

`e2e/journey/fungal-pathogenesis.spec.ts` is `test.fixme`, pointing at
[a chat turn can run for half an hour and then error](chat-turn-hangs-for-half-an-hour.md).
That is a product bug, not a test bug: no ceiling makes it green, and letting it
run holds a worker slot long enough to fail unrelated journeys beside it.

The accessibility half is done. Run 23's axe checkpoints named five nodes, all
fixed: `--destructive` failed 4.5:1 both as text (3.6:1 on white) and behind
white (the Stop button); `text-muted-foreground/70` read 3.04:1; the active
conversation row drew `text-primary` on `bg-primary/15` at 3.48:1; and the
ledger's scroll body had no keyboard access. `src/styles/statusTokens.test.ts`
holds the contrast thresholds for the solid tokens and, since the follow-up
sweep, fails on any source line that fades a status text token with an alpha
suffix, so neither the tokens nor their call sites regress below e2e.

# Adjudication of the next full run (2026-08-24)

**What I did.** Ran the 14 new reds standalone on the same stack, read each
first error, and rebuilt api and worker from the tree before the final pass.

**What I got.** Five specs died on `frame is not id/data/comment`: their route
mocks sent `data:`-only SSE, and PROTOCOL.md section 3 requires `id` plus
`data`. One spec died on a 422 whose error list named `errors`, `aborted`,
`finishReason` on a prior assistant message: the snapshot reduction's turn
facts, round-tripped by a rehydrated thread. The rest passed standalone:
auto-build 4/4, execution-phase, ai-workbench-integration, and the plasmodium
journey end to end in 1.8 minutes.

**Why that is wrong.** The mocks tested a wire shape the client rejects, the
request model refused the protocol's own reduction output, and the remaining
reds point at contention, not code.

**Why it happens.** The mock helpers predate the cursor protocol; pydantic-ai's
message union forbids unknown members; a full parallel run holds every worker
slot so feature specs' 15-20 s data-part waits starve.

**Fix.** Landed for the first two: `e2e/fixtures/sse.ts` emits conformant
frames, and `ChatRequestBody` parses the turn facts and stream part metadata
away (protocol 1.2.2). Open for the third: serialize turn-driving feature
specs like the journeys, or budget their waits against the contended band.

**What you would get.** A full run whose reds all mean product defects.
