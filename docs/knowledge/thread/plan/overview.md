---
type: Plan
title: Thread redesign plan overview
description: The plan that rebuilds PathFinder's conversation thread as a science-based reading surface - prose per turn, a quiet tool trace, flat figures, task rows, an approval card only when the user must act, and a dev mode behind the two dead settings flags - in four verified batches.
tags: [thread, conversation, pathfinder, plan, batches, ui, protocol, tokens]
generated: { by: claude-code/opus-5, at: 2026-08-29T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-29T00:00:00Z }
status: draft
---

# Thread redesign plan overview

> For agentic workers: implement batch by batch, task by task, per the batch
> documents in this directory. Every task follows red-green TDD and ends with
> its gates green. Do not start a batch before the prior batch's verifier
> reports are accepted. Batch 0 is written first and is frozen thereafter.

**Goal:** a researcher reads a turn the way they read a paper. One column of
prose says what was done and what it means. Under it, a single quiet line per
tool call says what that call did, in words and numbers, with no JSON. The
figures - a volcano, a subset preview, an enrichment table, a strategy link -
sit in the reading flow as figures, not as a stack of bordered boxes. A
long-running job is a task row with a label, a status and an elapsed time. The
user is asked to act exactly when the assistant needs an answer, and never
otherwise. Turning on two switches in Settings puts the raw JSON and the token
counts back, for whoever is debugging.

**The surface being replaced,** measured, not remembered:
`ToolCall` in `apps/web/src/features/conversation/content/MessageRenderer.tsx`
lines 83-109 wraps every tool call in an ai-elements `Tool` collapsible with a
border, and unconditionally renders `ToolInput` (the whole input object through
`JSON.stringify(args, null, 2)` in a Shiki code block) and `ToolOutput` (the
whole result). `SubAgentCallCard`
(`apps/web/src/features/conversation/content/parts/SubAgentCallCard.tsx`, 168
lines) is a second bordered card that nests one more `Tool` per sub-agent step,
with the same two JSON blocks each. Twenty-six `data-*` kinds are composed in
`content/contentComponents.ts` from `coreDataParts.ts` (13),
`strategyDataParts.ts` (10) and `edaDataParts.ts` (3); the ones that draw all
draw bordered cards.
`showRawToolCalls` and `showTokenUsage` are declared, defaulted and persisted in
`apps/web/src/state/useSettingsStore.ts` and read by nothing under
`features/conversation/**`.

## The shape in one paragraph

The wire learns one thing: a tool call may carry a one-line summary of what it
did, as a `data-tool-summary` chunk that patches the tool part it names. The
runtime and the headless client learn to reduce it, and the client gains one
pure derivation, `buildTrace`, that groups a message's parts into the trace the
thread draws. PathFinder's tools each write their own summary, at the tool,
where the numbers are. The thread gets six new components - `Trace`,
`TraceRow`, `TraceGroup`, `TaskRow`, `ApprovalCard`, `Figure` - and every
existing `data-*` renderer is restyled through `Figure` without losing a
testid. The token layer is rewritten once, with a light and a dark value for
every color including the chart set, under a `data-theme` attribute PathFinder
never sets. Nothing new architecturally: the summary rides the tool-return
metadata path the EDA parts already ride, and the trace is a reduction over
chunks that already exist.

## Layering (who may import whom)

```
packages/assistant-core   PROTOCOL.md, ui_message_reducer, stream part registry
packages/assistant-client-ts   reduce.ts, reduceTool.ts, message.ts, trace.ts
                                    |
apps/api/src/pathfinder/ai/tools/*  one summary per tool (the CONTENT)
                                    |
apps/web/src/lib/components/thread/ Trace, TraceRow, TraceGroup, TaskRow,
                                    ApprovalCard, Figure  (no @/features/*)
apps/web/src/features/conversation/thread/  the wiring and the part renderers
apps/web/src/styles/globals.css     the token layer
```

`assistant_core` owns the SHAPE and may not import `pathfinder`; its
`pyproject.toml` names no such dependency and its suite runs with no
`pathfinder` installed. PathFinder owns the CONTENT: every string that names a
gene, a strategy, a WDK search or a phase role is written in `apps/api`. The
`lib/components/thread/` components import protocol types and their own props
only, so a future shared UI package can lift them. `check-boundaries.mjs` does
not police `lib/` today (its rules run only for files under `features/`, and
seven `@/features/*` imports exist under `src/lib/`), so batch 2's verifier
grep is the gate for this rule. Import-linter stays at 8 kept contracts.

## The pinned contract

Every implementer and every verifier uses these exact names. A batch document
may refine a signature; it may not rename anything here.

### 1. The wire: `data-tool-summary`, protocol 1.4.0

A tool that knows what it did MAY say so in one line. The line rides its own
data chunk, emitted beside the call's terminal chunk:

```json
{
  "type": "data-tool-summary",
  "data": {
    "toolCallId": "call_a1",
    "summary": "6 of 12 Sample",
    "status": "ok"
  }
}
```

- `toolCallId: string` - the call this line describes. Required.
- `summary: string` - one line, ASCII, at most 120 characters, no trailing
  period, no JSON, no newline. Required and non-empty.
- `status: "ok" | "empty" | "warn"` - optional, default `"ok"`. `"empty"` says
  the call succeeded and found nothing, which is the failure mode a silent zero
  hides. `"warn"` says the call succeeded with a caveat the reader should see.
  A failed call needs no status: the tool part is already in `output-error`.

The chunk carries no `id`, so section 5.2's reconciliation does not apply; the
reduction rule below is what makes a second summary for one call replace the
first rather than append.

**Why a data chunk and not a field on `tool-output-available`.** The AI SDK's
`uiMessageChunkSchema`
(`apps/web/node_modules/ai/dist/index.mjs` line 5084 onward) declares every
tool chunk with `z.strictObject`. An extra `summary` key on
`tool-output-available` makes the SDK throw on the live stream, and the live
stream is the path `DurableChatTransport` uses: it re-frames accepted payloads
and hands them to `DefaultChatTransport.processResponseStream`, so the SDK's
reducer, not ours, builds the message a user watches arrive. Data chunks are
the one shape the SDK accepts open-endedly. `tool-input-start` and
`tool-input-available` do carry an SDK-native optional `title`, but it is set
before the tool runs and so cannot hold a result.

**Producer rule** (PROTOCOL section 6): a summary chunk for a `toolCallId` MAY
precede or follow that call's terminal chunk - `tool-output-available`,
`tool-output-error` or `tool-output-denied` - within the same turn. A reducer
addresses the summary by `toolCallId`, so the order does not matter. At most one
summary per call reaches the log, and a later summary for a call replaces an
earlier one.

The durable-tool path emits its summary from `chunks_from_result` BEFORE the
call's output chunk (`apps/api/src/pathfinder/ai/tools/durable.py` lines 96 to
116, at the `interrupt` resume). That is conforming.

**Reduction rule** (PROTOCOL section 9): `data-tool-summary` addresses the tool
part named by `data.toolCallId`. A conforming reducer sets that part's
`summary` and `summaryStatus` and appends no part. A summary naming a call the
client does not hold is ignored, under section 9's existing last rule. A second
summary for the same call replaces the first.

`assistant_core.conversation.ui_message_reducer` and
`packages/assistant-client-ts/src/core/reduce.ts` both implement it. The AI SDK
does not, and cannot be made to: on the live path the summary stays a
`data-tool-summary` part sitting beside its tool part in the same `parts`
array. `buildTrace` accepts both shapes and yields the same trace, which is
what makes one acceptance test cover both producers.

Version: PROTOCOL.md goes to `1.4.0` (additive: one data part, one reduction
rule). `packages/assistant-client-ts/src/protocol/version.ts` follows, and
`yarn sync:protocol` regenerates the vendored capture.

### 2. The trace grouping rule, stated once

`buildTrace(parts)` is pure, exported from `@pathfinder/assistant-client`, and
is the only place the rule lives.

Walk the message's ordered `parts` once, left to right.

1. A `text` part that carries content CLOSES the open run and is not part of
   it. Nothing else closes a run: prose is the only thing a reader reads
   between two stretches of work.
2. A `step-start` part, a `reasoning` part, and a `text` part whose text is
   empty are skipped and close nothing. A model that emits a reasoning item
   before every tool call (the OpenAI Responses models do, with an empty
   summary) would otherwise cut one turn's work into one-row traces.
3. A tool part joins the open trace as one row.
4. A `data-sub-agent-call` part opens or continues a GROUP keyed by its
   `data.toolCallId`, labeled by its `data.phase`, and carrying its
   `data.tokens` and `data.costUsd`.
5. A `data-sub-agent-step` part joins the group whose key equals its
   `data.parentToolCallId`. Steps merge into rows exactly as
   `mergeSubAgentSteps` in `apps/web/src/lib/utils/subAgentStep.ts` merges
   them: a `started` step carrying `args` and a later terminal step carrying
   `resultSummary` share a `toolCallId` and are one row.
6. A tool part with no group open belongs to the implicit group keyed
   `"lead"`, phase `"lead"`.
7. Consecutive rows in the same group stay in that group. A group is closed by
   rule 1, or by a `data-sub-agent-call` part with a different key.
8. A data part whose kind is in `renderingKinds` - a FIGURE - is HOISTED: it
   joins the open run's `figures` array in emission order and does NOT close
   the run. With no run open it opens a run that has zero rows. The host names
   the rendering kinds, because which parts draw is a product decision, and
   hoisting is what stops a turn's own outputs from cutting its trace into
   three pieces. The reader sees the calls, then what they produced.
   `data-turn-failed`, `data-turn-stopped` and `data-background-task-started`
   are NOT rendering kinds: the first two are notices the message renders at
   turn level, and the third is a task row (a trace element, not a figure). The
   host's `renderingKinds` set excludes all three explicitly, and the client
   acceptance asserts that a failure notice is not hoisted into `Trace.figures`
   and that the recorded turn yields exactly three figures.
9. A GROUP still `started` when the walk ends is closed by the turn, not by a
   chunk: `cancelled` when the parts carry `data-turn-stopped`, `failed` when
   they carry `data-turn-failed`, `superseded` when `turnEnded` says the turn
   is over and neither is there. The host owns `turnEnded` because only the
   host knows which message is the live one. A row still `running` inside a
   group closed `cancelled` or `failed` reads `stopped`; a `superseded` group
   keeps its running rows, because its work continues in the turn that
   resumes it. PROTOCOL.md section 6 states the same rule for any reader.
10. `data-tool-summary` parts and the non-rendering data kinds
    (`data-turn-usage`, `data-turn-status`, `data-lead-usage`,
    `data-scratchpad-updated`, `data-task-progress`, `data-task-completed`,
    `data-sub-agent-step`, `data-ledger-update`, `data-strategy-revision`)
    never become rows, never become figures, and never close a run.

The produced shape:

```ts
export type TraceRowStatus =
  | "running"
  | "ok"
  | "empty"
  | "warn"
  | "error"
  | "denied"
  | "awaiting-approval"
  | "stopped";

export interface TraceRow {
  key: string;
  toolCallId: string;
  toolName: string;
  summary: string | null;
  status: TraceRowStatus;
  input: unknown;
  output: unknown;
  errorText: string | null;
}

export interface TraceGroup {
  key: string;
  phase: string;
  rows: TraceRow[];
  tokens: number;
  costUsd: string;
  state: "started" | "completed" | "failed" | "cancelled" | "superseded";
}

export interface Trace {
  groups: TraceGroup[];
  figures: DataPart[];
  rowCount: number;
  running: boolean;
}

export function buildTrace(
  parts: readonly MessagePart[],
  options?: { renderingKinds?: ReadonlySet<string>; turnEnded?: boolean },
): Trace[];
```

`running` is true when any row's status is `running` or `awaiting-approval`,
so a run whose rows the turn stopped reports `false`. `rowCount` is the sum
over `groups` of `rows.length`.

A run exists only once it holds a row or a figure: a text part that closes an
empty run emits nothing, and a trailing text part after the last run opens no
run. `buildTrace` returns one `Trace` per non-empty run, in order, so the host can interleave
prose and traces exactly as they arrived.

### 3. The dev-mode rule

The two flags in `apps/web/src/state/useSettingsStore.ts` become the whole dev
mode, and nothing else gates on them.

- `showRawToolCalls` (default `false`): every `TraceRow` grows a disclosure
  that reveals the call's raw input and raw output, rendered by the existing
  ai-elements `ToolInput` and `ToolOutput`. With the flag off, no JSON text
  exists in the DOM for any tool call - not hidden behind a collapsible, not
  present and unstyled. This is a DOM assertion in the acceptance suite, not a
  styling one.
- `showTokenUsage` (default `true`, verified in `DEFAULTS` at
  `useSettingsStore.ts`): `ModelBadge` and the per-group token and cost suffix
  render only when it is on. The default is `true`, so turning the gate on
  changes nothing for an existing user; turning the switch off is the new
  behavior.

Nothing else in the thread reads a settings flag. A third flag is not added.

### 4. The theme rule

One token layer, defined once, in `apps/web/src/styles/globals.css`.

- Every color token has a light value on bare `:root` and a dark value under
  `:root[data-theme="dark"]`. No color is defined only in a dark block. The
  chart tokens (`--chart-1` through `--chart-6`, `--chart-positive`,
  `--chart-negative`) get their dark set, which closes
  the chart-token backlog item (`chart-tokens-have-no-dark-mode-values`, closed by batch 3).
- The mechanism is a `data-theme` attribute on `<html>`. **PathFinder never
  sets it.** There is no theme toggle, no `next-themes`, no theme provider.
  PathFinder ships light. The dark values exist so a host that does set the
  attribute gets a correct dark thread for free, and so no future dark work is
  a repaint of every consumer.
- **The `dark:` utilities must be rebound to the attribute.** There is no
  `@custom-variant dark` anywhere in the repo, so under Tailwind 4 the default
  `dark` variant compiles to `@media (prefers-color-scheme: dark)`. The 45
  `dark:` lines in TSX therefore fire today for any user whose OS is dark,
  against a fully light `:root` - a live inconsistency, not just a redesign
  concern. Batch 3 adds
  `@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));`
  in the same change that adds the dark block, so utilities and tokens share
  one switch.
- The `.dark` class selector is deleted; nothing ever sets that class. Its four
  shadow overrides move into the `[data-theme="dark"]` block, and
  `--shadow-inset` and `--shadow-glow`, which have no dark value today, gain
  one.
- **The dark block goes AFTER `:root` in the file.**
  `apps/web/src/styles/statusTokens.test.ts` reads `globals.css` as text and
  takes the FIRST `--token: H S% L%;` match. A dark block above `:root` would
  silently move the WCAG gate onto the dark palette.
- **The values are designed in OKLch and shipped as `H S% L%` triples.** The
  triple format is load-bearing in three places that this plan does not
  rewrite: `statusTokens.test.ts`'s regex and its HSL contrast math,
  `@theme inline`'s `hsl(var(--x))` wrappers, and `chartTheme.ts`'s
  `` `hsl(${raw})` `` wrapper. Each token carries its OKLch value in an ASCII
  comment beside it, so the next palette edit is done in the space the palette
  was reasoned in.
- Per-site brand accent keeps working, and is the one real conflict.
  `features/sites/siteTheme.ts` writes `--primary`, `--ring`, `--secondary`,
  `--accent` and `--muted` as INLINE styles on `document.documentElement`, and
  an inline style beats `[data-theme="dark"]`. `clampLightnessForWhiteText`
  only ever lowers lightness, and `--secondary`, `--accent` and `--muted` are
  written as hardcoded 93 to 96 percent lightness. Batch 3 makes
  `applySiteTheme` take the ground it is painting on, so the same brand hex
  yields a light set or a dark set. `useSiteTheme` depends on `[siteId]` only
  and never removes the properties; batch 3 leaves that alone, because
  PathFinder never flips the attribute.
- Semantic status stays separate from the accent: `--success`, `--warning`,
  `--destructive` and their foregrounds are their own scale and are never
  derived from the brand accent, because a site whose brand is red must not
  turn every error grey.

### 5. The figure style rules

A typed science part is a FIGURE in the prose flow, not a card.

- No border, no card background, no shadow, no rounded container. A figure is
  separated by a hairline rule above it (`border-t border-border/60`) and
  vertical space (`my-6`), nothing else.
- One accent per figure, at most. Color carries meaning (retained against
  dropped, pass against fail) or it is absent.
- A caption line under the figure, `text-xs text-muted-foreground`, carrying
  the numbers: "6 of 12 Sample, 34,320 of 68,640 pfal3D7 htseq counts",
  "1,543 of 5,511 genes retained at |log2FC| >= 1 and p <= 0.05". The numbers
  are the caption; the caption is not a label.
- **One entity-count format, everywhere.** A caption or a summary that reports
  entity counts writes one clause per entity,
  `` `${count.toLocaleString()} of ${unfilteredCount.toLocaleString()} ${entityDisplayName}` ``,
  and joins the clauses with `", "`. The display name is kept exactly as the
  wire gives it, never lowercased. This is one string shape shared by the
  figure captions and by `preview_eda_subset`'s tool summary, so a reader sees
  the same numbers written the same way in the trace and under the figure.
- The figure's own title is `text-sm font-medium`, on its own line, with no
  icon unless the icon distinguishes two figures of the same kind.
- Charts keep their existing testids and their `role="img"`.

### 6. The testids that must survive

A visual swap that drops one of these breaks a test, a frozen acceptance
module, or both. This is the union asserted by
`content/MessageRenderer.test.tsx`, `content/dataPartDispatch.test.tsx`, the
part-level suites, the frozen
`apps/web/src/acceptance/eda/batch67-parts.acceptance.tsx` and the frozen
`apps/web/e2e/acceptance/eda-journeys.spec.ts`:

```
tool-call-part, tool-think, tool-approval-controls, tool-approval-approve,
tool-approval-deny, tool-approval-decision, data-sub-agent-call,
data-background-task-started, data-task-progress, progress-bar-fill,
data-task-completed, data-memory-retrieved, data-conversation-title,
data-strategy-link, data-strategy-meta, data-graph-snapshot,
data-graph-cleared, data-gene-set, data-variant-comparison,
data-scored-comparison, data-verification-summary, data-enrichment-results,
data-eda-analysis-state, data-eda-filter-chip-N, data-eda-filter-overflow,
data-eda-subset-preview, data-eda-subset-note, data-eda-subset-bin-N,
data-eda-subset-coverage, data-eda-subset-multivalued,
data-eda-subset-histogram, data-eda-viz, data-eda-viz-empty,
data-eda-viz-unsupported-chart, eda-viz-volcano, eda-viz-volcano-selection,
eda-viz-volcano-genes, eda-viz-volcano-dropped, eda-viz-scatter,
eda-viz-scatter-count, consult-carousel, consult-slide,
consult-option-<label>, consult-note, consult-back, consult-next,
consult-submit, consult-recap, model-badge, superseded-badge, failure-notice,
stopped-notice, assistant-status, eda-viz-scatter-dropped,
message-composer, message-input, send-button, stop-button, add-attachment,
ledger-panel
```

`eda-viz-volcano`, `eda-viz-scatter` and their `-dropped` siblings are
authored by the chart components under `lib/components/charts/`, which take
the id as a `testId` prop; `data-eda-subset-histogram` is authored the same
way. Batch 2 changes the wrappers, not the charts.

`tool-call-part` survives on the `TraceRow` element: the row IS the tool call
part now. `data-task-progress` and `progress-bar-fill` survive inside
`TaskRow`. Existing negative assertions also survive: `data-task-progress` and
`data-task-completed` must still render no standalone card of their own, and
`plan-slot-answers`, `decision-answers`, `tool-approval-request` and
`tool-approval-result` must still be absent from the registry.

New testids this plan adds:

```
turn-trace, turn-trace-toggle, turn-trace-summary, trace-group,
trace-group-label, trace-group-usage, trace-row, trace-row-status,
trace-row-summary, trace-row-raw, task-row, task-row-status,
task-row-elapsed, approval-card, approval-card-title, figure,
figure-caption
```

### 7. Copy, fixed

The exact strings, so a test can assert them and two implementers cannot
disagree:

- Collapsed trace, one row: `1 step`
- Collapsed trace, many rows: `7 steps`
- Trace with a call still running: `Working...` (three ASCII periods)
- Trace with no call running and one waiting on the user's approval or
  answer: `Waiting for you`

  No elapsed time appears on the trace. The protocol puts no timestamp on a
  chunk, so a duration would exist only for the session that watched the turn
  arrive and would vanish on reload. A number that disappears is worse than no
  number.
- Group labels: ONE label set, in `apps/web/src/lib/models/phaseRoles.ts`.
  `lead: "Lead"`, `frame: "Frame"`, `build: "Build"`,
  `execution: "Build"` (an alias, so a log recorded before the wire was unified
  still reads), `verification: "Verification"`,
  `recover_failed_steps: "Recovery"`. No component holds a second map.
- Group usage suffix, from `formatUsage` in
  `apps/web/src/lib/utils/usageFormat.ts`: `formatUsage(12300, "0.004")`
  renders `12.3K`, a comma, a space, `$0.004` - the ASCII string
  `12.3K, $0.004`. The function separates with U+00B7 today; batch 2 changes it
  and its test to the comma form, and this literal is what every document and
  every test pins. A cost at or above one cent renders with two decimals, so
  `formatUsage(41800, "0.0131")` renders `41.8K, $0.01`.
- Row with no summary yet: the humanized tool name alone, from
  `humanizeToolName` in `apps/web/src/lib/utils/toolNames.ts`
- Row that failed: the humanized name, then the error text, truncated to 120
  characters on a word boundary with an ASCII `...`
- Raw disclosure label: `Raw` / hidden behind `showRawToolCalls`
- Approval card title: whatever `approvalPromptFor` returns for the tool,
  by default `<Tool label> needs your approval before it runs.`
- Approval buttons: `Deny`, `Approve` (unchanged)
- Task row while running: `<Tool label>` then `<percent>%`, and, when the
  started payload carried `estimatedDurationSeconds`, `~3 s` beside it. The
  label is `humanizeToolName(<the tool_name on the wire>)`; the enrichment task
  puts `geneset_enrichment` on the wire
  (`apps/api/src/pathfinder/ai/tools/standalone/workbench.py` line 146), so its
  label is `Gene set enrichment`
- Task row done: `Completed` or `Failed`
- Figure caption, analysis state:
  `6 of 12 Sample, 34,320 of 68,640 pfal3D7 htseq counts`
- Figure caption, subset preview: `6 of 12 Sample, 6 values`
- Figure caption, volcano: `1,543 of 5,511 genes retained`

## The acceptance layer

A frozen, behavior-only conformance suite written BEFORE batch 1 opens, by QA
agents who will implement nothing. It exists because an implementer's own tests
can mirror the implementation; the acceptance layer cannot, because it is
written from this contract and from values recorded in this repo, with no code
to mirror.

**Scope: stable boundaries only.** The reduced shape of one recorded turn, the
trace grouping over that turn's parts, the presence and absence of JSON in the
DOM under each flag, the figures and their captions, the task row, the approval
card, one route-mocked page journey, and the completeness of the token layer.
Never internals: no component prop shapes, no class names, no private helpers.
Assertions pin VALUES - `6 of 12`, `34,320 of 68,640`, `1,543 of 5,511`, `7
steps` - never just shapes.

**Where it lives.**

- Frontend: `apps/web/src/acceptance/thread/`, files named
  `*.acceptance.ts` / `*.acceptance.tsx` so the default vitest include
  (`src/**/*.{test,spec}.*`) never matches them. Run through the existing
  `vitest.acceptance.config.ts`, whose `include` gains
  `src/acceptance/**/*.acceptance.tsx` if it does not already cover it - that
  one config line is the only edit batch 0 makes to an existing acceptance
  file, and the lead makes it.
- Client package: `packages/assistant-client-ts/tests/acceptance/thread/`,
  run by the package's own `yarn test` only if the path is added to its vitest
  include; batch 0 adds a dedicated script `yarn test:acceptance` instead, so
  an implementer's `yarn test` stays green while the code does not exist.
  Each acceptance module opens with a dynamic import guarded by a
  `loadOrSkip` helper, exactly as the EDA frontend suite does.
- E2E: `apps/web/e2e/acceptance/thread-journeys.spec.ts`, wired into a
  `thread-acceptance` playwright project gated on `THREAD_ACCEPTANCE=1`, so a
  plain `npx playwright test` never executes it.
- Acceptance tests self-contain their fixtures inline. The one exception is
  the recorded turn, which is a checked-in JSON file the suite reads
  (`apps/web/src/acceptance/thread/recordedTurn.json`), because it is the
  artifact under test.

**The no-edit rule.** Implementers may not modify anything under
`apps/web/src/acceptance/**`, `apps/web/e2e/acceptance/**`,
`apps/web/vitest.acceptance.config.ts`, the `eda-acceptance` and
`thread-acceptance` projects in `apps/web/playwright.config.ts`, or
`packages/assistant-client-ts/tests/acceptance/**`. Every verifier's FIRST
check is a `diff -r` of each acceptance tree against the lead's frozen baseline
copy (the lead names its location in the verifier brief; git is not used in
this project's agent work): any difference is an automatic FAIL. A genuinely
wrong acceptance test is escalated to the session lead with evidence; the lead
is the only party who edits the suite, and records the correction in the batch
report.

**The frozen EDA suites are the regression net.**
`apps/web/src/acceptance/eda/**` and `apps/web/e2e/acceptance/eda-journeys.spec.ts`
already pin nine thread testids and their text. They are not edited by this
plan, and they are run at the close of batches 2 and 3 as the proof that the
restyle did not move the science.

**The exit criterion this adds to every batch:** the lead runs the batch's
acceptance module(s) and they pass unmodified. A batch does not close on green
implementer tests alone.

## Verification protocol

Every batch runs the same three-ring protocol:

1. **Implementers** (Opus, one per task column, parallel, worktree-isolated
   when files could touch) follow their task cards exactly: failing test first,
   minimal implementation, targeted gates, then the full suite for their app.
2. **Verifiers** (one Fable agent per batch) receive the implementers' claimed
   artifact lists and final reports. They re-run the FULL gate ladder from
   scratch, read every changed file, check each task card's steps against the
   diff, check the definition of done, and hunt for exactly the traps the batch
   document names. Two checks are universal, before any named trap:
   - **The acceptance no-edit check**: zero hunks under the acceptance paths.
   - **Mutation probes**: pick two or three behavior-bearing lines in the
     implementation, apply each mutation, run the implementer's tests. A
     mutation that no test kills is a FAIL. Revert the mutations; the probe
     list and each one's killing test go in the report.
   A verifier's report lists PASS/FAIL per task with evidence, never a summary
   alone.
3. **The session lead verifies the verifiers**: re-runs the gates once more,
   spot-reads the diffs against the batch document, and accepts or reopens the
   batch. A batch is closed only by ring 3.

## Global constraints (inherited by every task)

- TDD is non-negotiable: no production code without a failing test first.
- Only the LLM is mocked. Component tests use MSW against the real route paths;
  e2e uses recorded protocol-conformant SSE tails through
  `apps/web/e2e/fixtures/sse.ts` (`sseFrame`, `sseDone`,
  `uiMessageStreamHeaders`).
- Pydantic maximalism at every backend boundary: `model_validate`,
  discriminated unions, `extra="ignore"`; no isinstance chains, no `dict.get`
  ladders, no type suppressions, no `import as`.
- React: no `useEffect`, no `useMemo`, no `useCallback`, no `memo` (React
  Compiler is on; `eslint.config.cjs` refuses the three hooks through
  `no-restricted-imports`, and `memo` is this plan's rule, which the verifier
  greps for). Local UI state is `useState`, shared state is Zustand, server
  state is TanStack Query.
- `max-lines` is 300 per file, blank lines and comments skipped. The trace
  needs child components to stay under it.
- Components never call `fetch`; every request goes through `lib/api/`.
- Frontend boundaries (this plan's rule, checked by the verifier's grep;
  `scripts/check-boundaries.mjs` inspects `features/` files only): a file under
  `src/lib/components/thread/` may import its own tree, other `@/lib`,
  `@pathfinder/shared`, `@pathfinder/assistant-client`, `@/components/ui/*`,
  `@/components/ai-elements/*` and third-party. It may NOT import
  `@/features/*`, `@/state/*` or `@/app/*`. No entry is added to
  `CROSS_FEATURE_EXCEPTIONS`.
- `assistant_core` may not import `pathfinder`. Its suite runs in its own
  environment with no `pathfinder` installed, and that suite passing is the
  boundary.
- Import-linter stays at 8 kept contracts.
- Comments per the house rules: 1 to 3 lines, simple present tense, no
  narration, no history, no dates, no names. Near zero new comments.
- ASCII punctuation only, in code strings and in prose. No em dash, no en dash,
  no curly quotes, no unicode ellipsis. Use " - " and "...".
- After backend changes: `docker compose --env-file .env.dev up -d --build
  --force-recreate api worker`, then grep inside the container for a new symbol
  before claiming anything works.
- When Pydantic schemas or `KnownDataPartKind` change: `yarn generate:types`
  from the repo root, in the same task.
- Knowledge bundle discipline: docs updated in the same change that invalidates
  them. The backlog entry for this plan
  (`../../backlog/execute-thread-redesign-plan.md`) is removed by the task that
  finishes the work, and so is
  `chart-tokens-have-no-dark-mode-values` (closed by batch 3),
  which batch 3 closes.

## Batches

Four batches. Batch 0 is written first and frozen; batches 1 to 3 run in order.

| Batch | Document | Implementers | Verifiers |
|---|---|---|---|
| 0. The acceptance layer | [batch-0-acceptance-layer.md](batch-0-acceptance-layer.md) | 2 QA authors | lead freezes |
| 1. Protocol, runtime, client, tool summaries | [batch-1-protocol-and-summaries.md](batch-1-protocol-and-summaries.md) | 2 | 1 |
| 2. The thread | [batch-2-thread.md](batch-2-thread.md) | 2 | 1 |
| 3. Tokens and palette | [batch-3-tokens.md](batch-3-tokens.md) | 2 | 1 |

## The visual grammar borrowed, and what is not borrowed

The reference is Beautiful UI (`beautifului.dev`), read for its grammar, not
its code. What is taken:

- **Tool chips / thinking state**: one row per call, a small glyph, a verb, a
  monospace detail, a chevron; the whole block collapses to a single count line
  when it settles; rows enter with a short staggered `fade-up`. PathFinder's
  trace is this, with `summary` in place of their `chip`.
- **Task rows**: a status badge, a truncated label, a right-aligned amount, a
  status pill, a chevron; `done`, `running` and a failure that resolves.
  PathFinder's `TaskRow` is this, with percent and elapsed as the amount.
- **Approval card**: one question at a time, radio or checkbox indicators, a
  `Skip` and a `Continue`, a rolling counter, and a settled "Answers sent"
  state. `ConsultCarousel` already behaves this way and keeps its behavior and
  its testids; only its chrome changes.

What is NOT taken: their `foundation.json` token layer. It is a competing
system with its own names (`--page`, `--canvas`, `--ink`, `--ink-2`,
`--line-strong`, `--accent-tint`) and its own `.dark` class, and installing it
beside our `@theme inline` layer would give the app two sources of truth for
one color. Batch 3 writes our own values in OKLch, in our own names. Their
motion vocabulary (`fade-up`, `pop-in`, `fade-in`, 300 to 450 ms,
`cubic-bezier(0.23,1,0.32,1)`) is worth copying as timing; our `@utility`
blocks and `--animate-*` tokens are where it lands.
