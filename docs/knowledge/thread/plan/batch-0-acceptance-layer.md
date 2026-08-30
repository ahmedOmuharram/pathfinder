---
type: Plan
title: "Batch 0: the acceptance layer"
description: The frozen conformance suites, written before any implementation - one recorded turn pinned in vitest for the calm default and the dev mode, a protocol conformance case for the tool summary and the trace grouping, one route-mocked e2e journey, and the theme completeness test.
tags: [thread, pathfinder, plan, batch, acceptance, testing, frozen]
generated: { by: claude-code/opus-5, at: 2026-08-29T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-29T00:00:00Z }
status: accepted
---

# Batch 0: the acceptance layer

**Goal:** before one line of the redesign exists, write the tests that decide
whether it is correct, from [overview.md](overview.md)'s pinned contract and
from values recorded in this repo. Then freeze them.

**Who writes it:** two QA authors who will implement nothing in batches 1 to 3.
Author A owns the recorded turn and the frontend suite; Author B owns the
protocol conformance suite, the e2e journey and the theme test. The session
lead freezes the tree and takes the baseline copy.

**Read before starting:**

- [overview.md](overview.md) - the pinned contract. Names, copy and testids
  there are law.
- `apps/web/src/acceptance/eda/README.md` and
  `apps/web/src/acceptance/eda/batch67-parts.acceptance.tsx` - the shape to
  copy: `loadOrSkip`, inline fixtures, the no-edit banner.
- `apps/web/e2e/fixtures/sse.ts` - `sseFrame`, `sseDone`,
  `uiMessageStreamHeaders`. Every frame in this suite goes through them,
  because a hand-written frame that omits the `id:` line is rejected by the
  client and the failure looks like a rendering bug.
- `apps/web/e2e/feature/durable-verification.spec.ts` - the route-mocked chat
  tail this batch's e2e journey copies, including the composer selectors that
  actually exist (`message-input`, `getByRole("button", {name: /Send/i})`).
- `packages/assistant-client-ts/tests/conformance/reduce.test.ts` and
  `reduceTool.test.ts` - the conformance style: chunks in, message out, no
  mocks.

## Inherited constraints

Copied here so no author needs another file.

- ASCII punctuation only, in code strings and in prose.
- No type suppressions: no `as any`, `@ts-ignore`, `@ts-expect-error`,
  `eslint-disable`. `as any` is also refused by `scripts/check-boundaries.mjs`
  rule 2.
- `max-lines` 300 per file; split a suite before silencing the rule.
- tsconfig is `strict` with `noUncheckedIndexedAccess`,
  `exactOptionalPropertyTypes` and `noPropertyAccessFromIndexSignature`.
  Indexing an array yields `T | undefined`.
- Tests assert VALUES, not existence. `node scripts/check-weak-assertions.mjs`
  is a gate.
- No `useEffect`, `useMemo`, `useCallback` or `memo` in any test helper
  component.
- Acceptance files are self-contained: no import from a file an implementer
  will write, except through `loadOrSkip`.

## What this batch creates

**Create (frontend acceptance):**

- `apps/web/src/acceptance/thread/README.md`
- `apps/web/src/acceptance/thread/recordedTurn.json`
- `apps/web/src/acceptance/thread/support.ts`
- `apps/web/src/acceptance/thread/calm-default.acceptance.tsx`
- `apps/web/src/acceptance/thread/dev-mode.acceptance.tsx`
- `apps/web/src/acceptance/thread/figures.acceptance.tsx`
- `apps/web/src/acceptance/thread/theme.acceptance.ts`

**Create (client package acceptance):**

- `packages/assistant-client-ts/tests/acceptance/thread/toolSummary.acceptance.ts`
- `packages/assistant-client-ts/tests/acceptance/thread/trace.acceptance.ts`
- `packages/assistant-client-ts/vitest.acceptance.config.ts`

**Create (e2e):**

- `apps/web/e2e/acceptance/thread-journeys.spec.ts`

**Modify (lead only, once, at freeze time):**

- `apps/web/vitest.acceptance.config.ts` - its `include` already lists
  `src/acceptance/**/*.acceptance.ts` and `src/acceptance/**/*.acceptance.tsx`,
  so no edit is needed. Confirm this rather than assume it.
- `apps/web/playwright.config.ts` - add a `thread-acceptance` project, testDir
  `./e2e/acceptance`, `testMatch: process.env["THREAD_ACCEPTANCE"] === undefined
  ? /$^/ : /thread-journeys\.spec\.ts$/`, timeout 180_000,
  `fullyParallel: false`. The existing `eda-acceptance` project's `testMatch`
  is `/.*\.spec\.ts$/`, which would swallow the new file, so it is narrowed to
  `/eda-journeys\.spec\.ts$/` in the same edit. That narrowing is the ONLY
  change permitted to an existing acceptance artifact in this whole plan, and
  the lead makes it and records it.
- `packages/assistant-client-ts/package.json` - add
  `"test:acceptance": "vitest run --config vitest.acceptance.config.ts"`.

## Task 0.1: the recorded turn (Author A)

`apps/web/src/acceptance/thread/recordedTurn.json` is ONE assistant turn as a
JSON array of protocol chunks, in wire order. It is hand-built from real values
in this repo, because no capture in the tree contains a summary chunk yet. It
is the artifact every other frontend acceptance module reads.

Sources for the values, all real:

- The EDA payloads come verbatim from
  `apps/web/src/features/conversation/content/parts/edaPartFixtures.ts`:
  `EDA_ANALYSIS_STATE_FIXTURE` (heat shock study, `DS_e973eadd57`, entity
  counts 6 of 12 `Sample` and 34,320 of 68,640 `pfal3D7 htseq counts`),
  `EDA_SUBSET_PREVIEW_FIXTURE` (one entity, 6 of 12 `Sample`, distribution
  `Temperature` with 6 values), and
  `EDA_VOLCANO_VIZ_FIXTURE` (3 points, `PF3D7_0100200` retained).
- The volcano caption numbers `1,543 of 5,511` are the live-verified compute
  totals recorded in the EDA bundle; the recorded turn carries them on the
  viz part as `totalPoints: 5511`, `retainedPoints: 1543`, and its `points`
  array stays the three-point fixture, because a part may cap its points.
- `run_control_tests_on_step` and the task id
  `00000000-0000-0000-0000-0000000000aa` come from
  `e2e/feature/durable-verification.spec.ts`.
- Phase labels come from the one label set in
  `apps/web/src/lib/models/phaseRoles.ts`
  ([overview.md](overview.md) section 7).
- The two `data-sub-agent-step` `resultSummary` values are the inner tools' own
  `data-tool-summary` strings, lifted onto the step by `_forward_inner_event`
  (batch 1). No `data-tool-summary` chunk naming an inner call id appears in
  this file, because no reducer holds an inner call.

The exact chunk sequence, in order. Every `data-tool-summary` line is the
contract this plan adds, so its exact `summary` string is pinned here and by
batch 1's tool cards:

```
 1  start                    messageId 11111111-1111-1111-1111-111111111111
 2  data-turn-status         {label: "Thinking...", waitingOnLlm: true}
 3  text-start               id t1
 4  text-delta               "I looked at the heat shock study and subset it to the febrile samples."
 5  text-end                 id t1
 6  tool-input-start         call_1  search_eda_studies
 7  tool-input-available     call_1  {query: "heat shock", limit: 5}
 8  tool-output-available    call_1  {...}
 9  data-tool-summary        call_1  "3 studies matched heat shock"                      ok
10  tool-input-start         call_2  open_eda_analysis
11  tool-input-available     call_2  {datasetId: "DS_e973eadd57", purpose: "..."}
12  tool-output-available    call_2  {...}
13  data-eda.analysis-state  EDA_ANALYSIS_STATE_FIXTURE
14  data-tool-summary        call_2  "Opened Febrile samples on DS_e973eadd57"           ok
15  data-sub-agent-call      id sa_1  {toolCallId: sa_1, subAgent: frame_problem, phase: "frame", state: "started", modelId: "openai:gpt-5.6-luna", summary: "frame the heat shock question"}
16  data-sub-agent-step      {parentToolCallId: sa_1, kind: "tool", state: "started", toolCallId: s1, toolName: "search_for_searches", args: {query: "heat shock"}}
17  data-sub-agent-step      {parentToolCallId: sa_1, kind: "tool", state: "completed", toolCallId: s1, resultSummary: "12 searches"}
18  data-sub-agent-step      {parentToolCallId: sa_1, kind: "tool", state: "started", toolCallId: s2, toolName: "set_criterion", args: {criterionId: "c1", searchName: "GenesByText"}}
19  data-sub-agent-step      {parentToolCallId: sa_1, kind: "tool", state: "completed", toolCallId: s2, resultSummary: "c1 set to GenesByText"}
20  data-sub-agent-call      id sa_1  {..., state: "completed", succeeded: true, tokens: 12300, costUsd: "0.004"}
21  tool-input-start         call_3  preview_eda_subset
22  tool-input-available     call_3  {entityId: "ENT_8151325d", distributionVariableId: "VAR_7033e90f"}
23  tool-output-available    call_3  {...}
24  data-eda.subset-preview  EDA_SUBSET_PREVIEW_FIXTURE
25  data-tool-summary        call_3  "6 of 12 Sample"                                    ok
26  tool-input-start         call_4  run_control_tests_on_step
27  tool-input-available     call_4  {wdkStepId: 132}
28  data-background-task-started  {taskId: 0000...aa, toolName: "run_control_tests_on_step", estimatedDurationSeconds: 3}
29  data-task-progress       id 0000...aa  {taskId: 0000...aa, percent: 0.66, message: "Comparing controls"}
30  data-task-completed      {taskId: 0000...aa, status: "success"}
31  tool-output-available    call_4  {...}
32  data-tool-summary        call_4  "8 of 10 positive controls recovered"               ok
33  tool-input-start         call_5  optimize_search_parameters
34  tool-input-available     call_5  {target: {...}, controls: {...}}
35  tool-approval-request    approvalId call_5, toolCallId call_5
36  data-eda.viz             EDA_VOLCANO_VIZ_FIXTURE with totalPoints 5511, retainedPoints 1543
37  text-start               id t2
38  text-delta               "Approve the parameter sweep and I will run it."
39  text-end                 id t2
40  data-lead-usage          id lu_1  {modelId: "openai:gpt-5.6-luna", tokens: 41800, costUsd: "0.0131"}
41  finish                   finishReason "stop"
42  done
```

**What the file pins by construction.** One trace run: the opening text closes
nothing (no run is open yet), the closing text ends the run, an empty run is
never emitted, and rule 8 hoists the figures:

- The run - opened by chunk 6, closed by chunk 37. Groups in order:
  `lead` (rows `call_1`, `call_2`), `sa_1` (phase `frame`, rows `s1`, `s2`,
  12300 tokens, `$0.0131` is the LEAD's, `$0.004` is the group's), `lead`
  (rows `call_3`, `call_4`, `call_5`). `rowCount` 7. `figures` in emission
  order: `data-eda.analysis-state`, `data-eda.subset-preview`, `data-eda.viz`.
  `running` true, because `call_5` is `awaiting-approval`.
- The two text parts are NOT in any run.

**Traps for this task, named:**

- The `data-sub-agent-call` chunks at 15 and 20 carry the same `id`, so
  section 5.2 reconciles them into ONE part. Two parts means the fixture is
  wrong.
- `data-task-progress` at 29 carries the task id as its `id`, and
  `data-background-task-started` and `data-task-completed` carry none. Getting
  this backwards breaks `DataBackgroundTaskStarted`, which re-derives both by
  scanning parts.
- Chunk 35 arrives with no output for `call_5`. The part must end in
  `approval-requested`, not `output-available`.
- `finishReason` is `stop` even though a call is suspended on an approval:
  section 6.2 says the turn closes normally.
- Chunks 28 to 31 collapse section 6.1's durable lifecycle into one turn. On
  the wire the suspending turn closes with `finishReason: "other"`, the
  progress and completion land in the gap, and the continuation opens a second
  `start` with the SAME `messageId`; `reduceSnapshot`'s `ThreadBuilder` only
  flushes when the `messageId` changes, so the reduced message is the same.
  `e2e/feature/durable-verification.spec.ts` collapses it the same way.
- A summary chunk MAY precede or follow its call's terminal chunk, so chunk 32
  standing after chunk 31 is one of two conforming orders. The durable-tool
  path emits its summary from `chunks_from_result` BEFORE the output chunk;
  neither order changes the reduced part, because the reducer addresses by
  `toolCallId`. No assertion in this suite may depend on the order.

## Task 0.2: the calm default (Author A)

`apps/web/src/acceptance/thread/calmDefault.acceptance.tsx`.

`loadOrSkip.ts` is a few lines of shared plumbing. The EDA suite's
`acceptance/eda/support.ts` takes a module specifier string; this one takes a
loader thunk so the import path stays statically analysable:

```ts
export async function loadOrSkip<T>(load: () => Promise<T>): Promise<T | null> {
  try {
    return await load();
  } catch {
    return null;
  }
}
```

Every module calls it in `beforeAll` and calls `it.skip` when it yields null,
so the suite is a clean skip until batch 2 lands and never a red the
implementer must ignore.

The module reduces `recordedTurn.json` through `reduceSnapshot` from
`@pathfinder/assistant-client` (already a dependency of `apps/web` through the
tsconfig path), renders the resulting message through the thread's real
renderer with `showRawToolCalls: false` and `showTokenUsage: true`, and
asserts:

1. `getByTestId("turn-trace")` exists exactly once per run: one run, so
   `getAllByTestId("turn-trace")` has length 1.
2. `getByTestId("turn-trace-summary")` reads `Working...` on the recorded turn (its last call is awaiting approval, so the run is running) and `7 steps` on the settled continuation (`SETTLED_CHUNKS`: the same turn plus the approval continuation of PROTOCOL 6.2).
3. `getAllByTestId("trace-row")` has length 7. The labels
   come from `humanizeToolName`, and `search_eda_studies` is NOT in
   `TOOL_LABELS`, so it humanizes to `Search eda studies`. Pin the humanized
   strings the function actually returns today, and pin the summary beside
   each:
   ```
   Search eda studies      3 studies matched heat shock
   Open eda analysis       Opened Febrile samples on DS_e973eadd57
   Search catalog          12 searches
   Set criterion           c1 set to GenesByText
   Preview eda subset      6 of 12 Sample
   Run control tests       8 of 10 positive controls recovered
   Optimize parameters
   ```
   The last row has no summary because it never ran.
4. `getAllByTestId("trace-group-label")` reads `Lead`, `Frame`, `Lead`.
5. `getByTestId("trace-group-usage")` inside the Frame group reads exactly
   `12.3K, $0.004` - the ASCII comma-and-space form batch 2 gives `formatUsage`
   (overview section 7). Pin that literal. Importing `formatUsage` for the
   expected value stays fine, but the literal is the contract.
6. **No JSON anywhere.** `container.textContent` does not contain `"datasetId"`,
   `"DS_e973eadd57"` as a bare key-value, `"{"` followed by `"\n"`, or the
   string `wdkStepId`. Assert the negative on `container.textContent`, not on a
   query, so a hidden collapsible fails too. This is the assertion the whole
   redesign turns on.
7. `getByTestId("task-row")` exists once, its status reads `Completed`, and
   `getByTestId("progress-bar-fill")` still exists. A second, inline case
   renders a started payload whose `toolName` is `geneset_enrichment` - the
   name the wire carries
   (`apps/api/src/pathfinder/ai/tools/standalone/workbench.py` line 146) - and
   asserts the row's label reads exactly `Gene set enrichment`.
8. `getByTestId("approval-card")` exists once and its title reads
   `Optimize parameters needs your approval before it runs.`;
   `getByTestId("tool-approval-approve")` and
   `getByTestId("tool-approval-deny")` are both present.
9. `getByTestId("model-badge")` is present and reads `41.8K, $0.01`:
   `formatCost` renders a cost at or above one cent with two decimals, so
   `0.0131` is `$0.01`, not `$0.0131`, and the separator is the ASCII comma and
   space.
10. `queryByTestId("data-task-progress")` renders no standalone card OUTSIDE
    the task row, exactly as `dataPartDispatch.test.tsx` asserts today.

## Task 0.3: the dev mode (Author A)

`apps/web/src/acceptance/thread/devMode.acceptance.tsx`, same recorded turn.

1. With `showRawToolCalls: true`: each of the seven `trace-row` elements
   exposes a `trace-row-raw` region, and `container.textContent` DOES contain
   `wdkStepId` and `DS_e973eadd57`. Assert the count of `trace-row-raw`
   elements is 7, so a single global JSON dump does not pass.
2. With `showRawToolCalls: false` again after a re-render: zero
   `trace-row-raw` elements and the negative text assertion of task 0.2 holds.
   Flipping the flag back must not leave the DOM dirty.
3. With `showTokenUsage: false`: `queryByTestId("model-badge")` is null and
   `queryAllByTestId("trace-group-usage")` is empty.
4. With `showTokenUsage: true`: both are present. This is the default, so
   turning the gate on changes nothing for an existing user, and this case
   proves it.

## Task 0.4: the figures (Author A)

`apps/web/src/acceptance/thread/figures.acceptance.tsx`. Mocks
`@/lib/components/charts/echartsRegistry` exactly as
`apps/web/src/acceptance/eda/batch67-parts.acceptance.tsx` does, then asserts
against the same recorded turn:

1. `getAllByTestId("figure")` has length 3, in emission order, and each is a
   descendant of the run's container, AFTER `turn-trace` in DOM order.
2. The three figures carry, in order, `data-eda-analysis-state`,
   `data-eda-subset-preview` and `data-eda-viz` as descendants. Every one of
   those testids survives.
3. `getAllByTestId("figure-caption")` reads, in order:
   - `6 of 12 Sample, 34,320 of 68,640 pfal3D7 htseq counts`
   - `6 of 12 Sample, 6 values` (the preview carries one entity, then the
     distribution the fixture supports)
   - `1,543 of 5,511 genes retained`

   Both entity-count captions use the one format of overview section 5: one
   clause per entity, `count of unfilteredCount entityDisplayName`, thousands
   separated, joined by `", "`, with the display name exactly as the wire gives
   it. `Sample` and `pfal3D7 htseq counts` are asserted with their own casing;
   a lowercased `samples` or a substituted `rows` is a FAIL.
4. `getByTestId("eda-viz-volcano")` carries `role="img"`.
5. **No figure has a border.** Assert on computed style is brittle in jsdom, so
   assert on the class contract instead: no element carrying `data-testid=
   "figure"` has a class matching `/\bborder\b|\brounded-lg\b|\bshadow-card\b/`,
   and every one has a class matching `/\bborder-t\b/`. This is the one
   styling assertion in the suite and it is named as such.
6. `data-eda-filter-chip-0` and `data-eda-subset-coverage` are still present,
   because the frozen EDA suite asserts them and this suite must not disagree
   with it.

## Task 0.5: the protocol conformance cases (Author B)

`packages/assistant-client-ts/tests/acceptance/thread/toolSummary.acceptance.ts`:

1. `reduceTurn` over `[tool-input-start, tool-input-available,
   tool-output-available, data-tool-summary]` yields ONE part. Its `type` is
   `tool-preview_eda_subset`, its `state` is `output-available`, its `summary`
   is `6 of 12 Sample` and its `summaryStatus` is `ok`.
2. A `data-tool-summary` naming a `toolCallId` the reducer does not hold adds
   no part and throws nothing. `parts.length` is unchanged.
3. A second `data-tool-summary` for the same call REPLACES the first.
   `parts.length` is unchanged and `summary` is the second string.
4. `data-tool-summary` with `status: "empty"` sets `summaryStatus` to
   `"empty"`; with no `status` it defaults to `"ok"`.
5. A summary chunk arriving BEFORE the output still patches the part, because
   the reducer addresses by id and not by order. Both orders conform: the
   durable-tool path emits its summary from `chunks_from_result` before the
   call's output chunk, and the metadata path emits it after. Assert that the
   two orders yield a deeply equal part.
6. `HANDLED_CHUNK_KINDS` does not need the kind, because `isDataChunk` already
   routes it; assert that `isKnownChunkKind("data-tool-summary")` is true, so
   `DurableChatTransport` forwards it rather than dropping it.
7. `PROTOCOL_VERSION` is `1.4.0`.

`packages/assistant-client-ts/tests/acceptance/thread/trace.acceptance.ts`
drives `buildTrace` over the SAME chunk array as
`recordedTurn.json` (inlined, per the self-containment rule) and asserts:

1. `buildTrace(parts, {renderingKinds})` returns exactly 1 run (an empty run
   is never emitted).
2. The run has `rowCount` 7, `running` true, `figures.length` 3.
3. The run's groups are `["lead", "sa_1", "lead"]` by key and
   `["lead", "frame", "lead"]` by phase.
4. The `sa_1` group has `tokens` 12300, `costUsd` `"0.004"`, `state`
   `"completed"`, and 2 rows whose `toolName`s are `search_for_searches` and
   `set_criterion` and whose `summary`s are `12 searches` and
   `c1 set to GenesByText`.
5. Row `call_5` has `status` `"awaiting-approval"` and `summary` null.
6. **The two producers agree.** Build the same message a second way - through
   the AI SDK path shape, where `data-tool-summary` survives as its own data
   part beside the tool part rather than being folded into it - and assert
   `buildTrace` returns a deeply equal result. This is the single test that
   makes one component correct on both the live stream and a reload.
7. A text part between two tool parts splits them into two runs.
8. A `step-start` part between two tool parts does not.
9. A `data-turn-status` part between two tool parts does not.
10. **A failure notice is not a figure.** `data-turn-failed` and
    `data-turn-stopped` are notices the message renders at turn level, so the
    host's `renderingKinds` set excludes them. Build a run holding a tool part
    and a `data-turn-failed` part, pass the same `renderingKinds` the host
    passes, and assert `figures` is empty and `rowCount` is 1.

## Task 0.6: the e2e journey (Author B)

`apps/web/e2e/acceptance/thread-journeys.spec.ts`, one test, modeled line for
line on `e2e/feature/durable-verification.spec.ts`: open a conversation through
`POST /api/v1/conversations/open`, `page.route("**/api/v1/chat", ...)` with the
recorded turn's chunks joined through `sseFrame` and terminated by `sseDone()`,
`uiMessageStreamHeaders()` on the response, then type into `message-input` and
press Enter.

Asserts on the real page:

1. `getByTestId("turn-trace-summary")` reads `Working...` (the recorded turn ends awaiting approval).
2. `getByTestId("trace-row")` has count 7 and the first contains
   `3 studies matched heat shock`.
3. `page.locator("body")` text does NOT contain `wdkStepId`.
4. `getByTestId("task-row")` contains `Completed`.
5. `getByTestId("approval-card")` is visible and
   `getByTestId("tool-approval-approve")` is enabled.
6. `getByTestId("eda-viz-volcano")` is visible.
7. Expanding: `getByTestId("turn-trace-toggle").click()` toggles the rows'
   visibility, asserted with `toBeVisible` / `toBeHidden` and not with a class
   check. One run renders, so the locator is unique.

Strict mode is respected: every locator is made specific, never `.first()`,
`.nth()` or `.last()`.

## Task 0.7: the theme test (Author B)

`apps/web/src/acceptance/thread/theme.acceptance.ts`. Reads
`src/styles/globals.css` as text, exactly as `statusTokens.test.ts` does, and
asserts:

1. **Every color token has both values.** Parse the bare `:root { ... }` block
   and the `:root[data-theme="dark"] { ... }` block. The set of property names
   that look like a color (a `H S% L%` triple, an `rgb(...)`, an `oklch(...)`
   or a `#hex`) in the light block equals the set in the dark block. Report the
   difference by name when it fails, both directions.
2. **No `.dark` selector exists.** `/^\s*\.dark\b/m` does not match, and
   `.dark .specialist-rail-validate` and `.dark .specialist-rail-research` are
   gone with it.
3. **No color is defined only in a media query.** The only `@media` block is
   `prefers-reduced-motion`, and it sets no property whose name matches
   `/color|background|border|--(chart|kind|primary|accent|muted|success|warning|destructive|foreground|card|popover|sidebar|ring|input)/`.
4. **The dark block comes after `:root`.** `indexOf(':root[data-theme="dark"]')`
   is greater than `indexOf(':root {')`. This is what keeps
   `statusTokens.test.ts` measuring the light palette.
5. **The custom variant is declared.**
   `/@custom-variant\s+dark\s*\(/` matches, and its body names
   `[data-theme="dark"]`.
6. **The chart tokens have a dark set.** All eight of `--chart-1` through
   `--chart-6`, `--chart-positive` and `--chart-negative` appear in the dark
   block.
7. **`chartTheme.ts` has no hardcoded light palette left.** Read
   `src/lib/components/charts/chartTheme.ts` as text and assert it contains no
   `hsl(` literal. The fallbacks must come from somewhere the theme reaches.
8. **The status tokens keep their format.** `--destructive`, `--success` and
   `--warning` still match `/--success:\s*[\d.]+\s+[\d.]+%\s+[\d.]+%\s*;/` in
   the light block, because `statusTokens.test.ts` throws otherwise.

## Section close-out

- [ ] `cd apps/web && npx tsc --noEmit && npx eslint src/ e2e/ && node scripts/check-boundaries.mjs`
- [ ] `cd apps/web && npx vitest run` - the DEFAULT run must not collect one
  acceptance file. Report the collected count before and after this batch; the
  numbers must be equal.
- [ ] `cd apps/web && npx vitest run --config vitest.acceptance.config.ts` -
  every thread module SKIPS cleanly, every EDA module PASSES. Report both
  counts.
- [ ] `cd packages/assistant-client-ts && yarn typecheck && yarn lint && yarn test` -
  the default test run must not collect the acceptance directory. Then
  `yarn test:acceptance` and report that both thread modules skip.
- [ ] `cd apps/web && npx playwright test` - `thread-journeys.spec.ts` is not
  collected. Then `THREAD_ACCEPTANCE=1 npx playwright test --project=thread-acceptance`
  and report that it runs and fails on missing testids, which is the correct
  red for a suite whose implementation does not exist.
- [ ] `EDA_ACCEPTANCE=1 npx playwright test --project=eda-acceptance` still
  collects exactly `eda-journeys.spec.ts` after the `testMatch` narrowing.
- [ ] Report: every assertion that pins a literal string, with the file and
  line; any assertion that pins a shape rather than a value, with why.

## Verifier

Re-run:

```
cd /Users/ahmedmuharram/repos/pathfinder/apps/web
npx tsc --noEmit
npx eslint src/ e2e/
node scripts/check-boundaries.mjs
node scripts/check-weak-assertions.mjs
npx vitest run
npx vitest run --config vitest.acceptance.config.ts
cd /Users/ahmedmuharram/repos/pathfinder/packages/assistant-client-ts
yarn typecheck && yarn lint && yarn test && yarn test:acceptance
node /Users/ahmedmuharram/repos/pathfinder/scripts/check-knowledge.mjs
```

Traps, by name:

1. **An acceptance file collected by a default run.** Grep the default vitest
   output for `acceptance`. One hit is a FAIL: it makes every batch red before
   it starts.
2. **`eda-acceptance` swallowing the new spec.** Its `testMatch` was
   `/.*\.spec\.ts$/`. If the narrowing was missed, `EDA_ACCEPTANCE=1` now runs
   the thread journey too.
3. **An acceptance test that imports an implementer's file directly**, rather
   than through `loadOrSkip`. It turns a clean skip into a red.
4. **A fixture imported from `features/conversation/content/parts/edaPartFixtures.ts`**
   rather than inlined into `recordedTurn.json`. An implementer may edit that
   file; the acceptance layer may not depend on one.
5. **A frame written by hand** instead of through `sseFrame`. Grep the e2e
   spec for `data:` outside the helper.
6. **The `data-sub-agent-call` chunks not sharing an `id`**, which yields two
   parts and a wrong `rowCount`.
7. **`data-background-task-started` given an `id`**, which breaks
   reconciliation.
8. **An assertion on a class name** anywhere except task 0.4 item 5, which is
   the one licensed exception.
9. **A weak assertion**: `toBeTruthy`, `toBeDefined`, `not.toBeNull` where a
   value was available. `check-weak-assertions.mjs` is the gate; read its
   output, do not just run it.
10. **Smart punctuation** in any new file, including inside a JSON string.
11. **A test that would pass against today's code.** Every thread module must
    skip or fail today. A green thread acceptance module before batch 2 means
    it asserts nothing.
12. **`.first()` or `.nth()` used to dodge Playwright strict mode.** One
    licensed use, named in task 0.6.

Mutation probes are not run in this batch: there is no implementation to
mutate. Instead, the verifier runs the INVERSE probe: take
`recordedTurn.json`, change `retainedPoints` from 1543 to 1544, and confirm
that `figures.acceptance.tsx`'s caption assertion would fail. Revert. Report
the probe and the assertion that would have caught it.

Report format, mandatory:

```
Batch 0 verification

Gates
  tsc --noEmit                   PASS/FAIL  <first error if FAIL>
  eslint src/ e2e/               PASS/FAIL  <count>
  check-boundaries.mjs           PASS/FAIL  <count>
  check-weak-assertions.mjs      PASS/FAIL  <count>
  vitest run (default)           PASS/FAIL  <passed>/<total>, acceptance collected: <n>
  vitest run (acceptance config) PASS/FAIL  <thread skipped>/<eda passed>
  client yarn test               PASS/FAIL  <passed>/<total>
  client yarn test:acceptance    PASS/FAIL  <skipped>
  playwright (default)           PASS/FAIL  thread-journeys collected: yes/no
  check-knowledge.mjs            PASS/FAIL

Per task
  0.1 recordedTurn.json      PASS/FAIL  <evidence>
  0.2 calmDefault            PASS/FAIL
  0.3 devMode                PASS/FAIL
  0.4 figures                PASS/FAIL
  0.5 protocol conformance   PASS/FAIL
  0.6 e2e journey            PASS/FAIL
  0.7 theme                  PASS/FAIL

Pinned values  (each literal string asserted, with file:line)

Traps  (1 to 12, each CLEAN or the file:line that violates it)

Inverse probe  (the mutation, the assertion that catches it)

Definition of done
  zero debt            YES/NO  <what remains>
  adjacent reconciled  YES/NO
  every module red or skipped today  YES/NO
```

## Exit criteria

For the session lead to freeze batch 0:

1. Every gate green, verified by the lead's own run.
2. A default `npx vitest run` in `apps/web` collects zero acceptance files, and
   a default `npx playwright test` collects zero acceptance specs.
3. Every thread acceptance module skips cleanly today, and the e2e journey
   fails on missing testids rather than on a harness error.
4. `EDA_ACCEPTANCE=1 npx playwright test --project=eda-acceptance` still runs
   exactly `eda-journeys.spec.ts`, and the frozen EDA vitest modules still
   pass unmodified.
5. `recordedTurn.json` carries the real EDA payloads, the real task id, the
   real phase labels and the seven pinned summary strings, and the lead has
   read every one of them against its source.
6. The lead takes the frozen baseline copy of
   `apps/web/src/acceptance/`, `apps/web/e2e/acceptance/`,
   `apps/web/vitest.acceptance.config.ts`, `apps/web/playwright.config.ts` and
   `packages/assistant-client-ts/tests/acceptance/` into the session
   scratchpad, and names that location in every later verifier brief.
