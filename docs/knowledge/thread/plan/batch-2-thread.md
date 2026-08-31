---
type: Plan
title: "Batch 2: the thread"
description: The reading surface itself - a quiet trace of one line per tool call, flat figures in the prose flow, task rows for durable jobs, an approval card only when the user must act, the two dead settings flags wired up as the dev mode, and every bordered card removed.
tags: [thread, pathfinder, plan, batch, frontend, conversation, components]
generated: { by: claude-code/opus-5, at: 2026-08-29T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-29T00:00:00Z }
status: accepted
---

# Batch 2: the thread

**Goal:** a turn reads as prose with a quiet trace under it, figures in the
flow, and a question only when there is one. No JSON unless a switch is on.

**Prerequisites:** batch 1 closed. This batch consumes `buildTrace`,
`Trace`, `TraceGroup`, `TraceRow` and `TraceRowStatus` from
`@pathfinder/assistant-client` by those exact names, and every tool now emits
its summary.

**Read before starting:**

- [overview.md](overview.md) - sections 2, 3, 5, 6 and 7 are law. Section 6's
  testid list and section 7's copy are asserted verbatim by the frozen suite.
- [batch-0-acceptance-layer.md](batch-0-acceptance-layer.md) tasks 0.2, 0.3 and
  0.4 - the exact assertions this batch must satisfy.
- `apps/web/src/features/conversation/content/MessageRenderer.tsx` - the whole
  visual contract today, and the file this batch edits most.
- `apps/web/src/features/conversation/content/parts/SubAgentCallCard.tsx`,
  `ToolApprovalControls.tsx`, `DataBackgroundTaskStarted.tsx`,
  `DataTaskProgress.tsx` - the four components the trace absorbs.
- `apps/web/src/features/conversation/runtime/chatHelpersContext.ts` - how a
  part reaches `chat.messages`. `ToolApprovalControls` line 55 is the
  precedent.
- `apps/web/src/components/ai-elements/tool.tsx` and `message.tsx` - the
  vendored primitives; `MessageResponse` (Streamdown) is exported and used by
  `rail/LedgerPanelDetail.tsx` only, not by the thread.

## The rendering strategy, decided

**`MessagePrimitive.Content` stays.** The trace is rendered IN PLACE by an
anchor.

assistant-ui renders a message's parts one at a time through the components
map. Its one grouping hook, `components.ToolGroup`
(`@assistant-ui/core/dist/react/primitives/message/MessageParts.js`,
`groupMessageParts`), wraps CONSECUTIVE `tool-call` parts only: a `data` part
between two calls ends the group, so `data-sub-agent-call`, the sub-agent steps
and every figure would split a turn's trace into pieces. It cannot express the
overview's grouping rule. Replacing `MessagePrimitive.Content` would delete
`dataPartDispatch.test.tsx`'s guarantee that the map is total, which is the
strongest lock in the thread today. Instead:

- `tools.Fallback` and `tools.by_name.think` both render `TraceAnchor`.
- `data-sub-agent-call` renders `TraceAnchor` too.
- `TraceAnchor` reads the whole message from `chat.messages`, runs
  `buildTrace`, finds the run that contains its own part, and renders the ENTIRE
  `<Trace>` block only when its part is the run's first ROW-BEARING part: the
  first tool part or `data-sub-agent-call` part of that run. A figure that
  opens a run (overview rule 8) renders no anchor, so "first element" would
  never draw that run's trace. Every other row-bearing part of that run
  renders `null`.
- Figures keep their own registry entries and render at their own positions,
  which is after the whole trace block, which is what
  [overview.md](overview.md) rule 8 calls hoisting. The two mechanisms agree by
  construction; `Trace.figures` exists for a consumer that renders standalone
  and is what the client-package acceptance module asserts.

**The degraded mode is specified, not accidental.** `useChatHelpersOptional()`
returns null outside a `ChatHelpersProvider`, which is how
`MessageRenderer.test.tsx` and `dataPartDispatch.test.tsx` render today. With
no helpers, `TraceAnchor` renders a single-row trace for its own part, carrying
the same testids. Those two suites keep working and keep meaning something.

## Inherited constraints

- No `useEffect`, `useMemo`, `useCallback` or `memo`. React Compiler is on.
- `max-lines` 300 per file. `Trace.tsx` will not fit one file; split it.
- `@typescript-eslint/strict-boolean-expressions`,
  `no-unnecessary-condition`, `switch-exhaustiveness-check`,
  `consistent-type-imports`, `no-console` except `warn` and `error`.
- tsconfig `strict` + `noUncheckedIndexedAccess` +
  `exactOptionalPropertyTypes` + `noPropertyAccessFromIndexSignature`.
- No type suppressions. No `as any`.
- **Boundaries:** a file under `src/lib/components/thread/` may import its own
  tree, other `@/lib`, `@pathfinder/shared`, `@pathfinder/assistant-client`,
  `@/components/ui/*`, `@/components/ai-elements/*` and third-party. It may NOT
  import `@/features/*`, `@/state/*` or `@/app/*`. No entry is added to
  `CROSS_FEATURE_EXCEPTIONS`; needing one means the code is in the wrong layer.
  This is what lets a future shared UI package lift these files unchanged.
- Components never call `fetch`.
- ASCII punctuation only. Near-zero comments.
- Gate ladder for every task:

```
cd /Users/ahmedmuharram/repos/pathfinder/apps/web
npx tsc --noEmit
npx eslint src/
node scripts/check-boundaries.mjs
node scripts/check-weak-assertions.mjs
npx vitest run <exact test files for this task>
```

## Implementer A: the trace, the task row, the approval card

### Files

**Create**

- `apps/web/src/lib/components/thread/Trace.tsx`
- `apps/web/src/lib/components/thread/TraceGroup.tsx`
- `apps/web/src/lib/components/thread/TraceRow.tsx`
- `apps/web/src/lib/components/thread/traceGlyphs.tsx`
- `apps/web/src/lib/components/thread/TaskRow.tsx`
- `apps/web/src/lib/components/thread/ApprovalCard.tsx`
- `apps/web/src/features/conversation/thread/TraceAnchor.tsx`
- `apps/web/src/features/conversation/thread/traceRenderingKinds.ts`
- `apps/web/src/features/conversation/thread/useThreadDevMode.ts`

**Test**

- `apps/web/src/lib/components/thread/Trace.test.tsx`
- `apps/web/src/lib/components/thread/TraceRow.test.tsx`
- `apps/web/src/lib/components/thread/TaskRow.test.tsx`
- `apps/web/src/lib/components/thread/ApprovalCard.test.tsx`
- `apps/web/src/features/conversation/thread/TraceAnchor.test.tsx`

**Modify**

- `apps/web/src/features/conversation/content/MessageRenderer.tsx`
- `apps/web/src/features/conversation/content/MessageRenderer.test.tsx`
- `apps/web/src/features/conversation/content/coreDataParts.ts`
- `apps/web/src/features/conversation/content/parts/DataBackgroundTaskStarted.tsx`
- `apps/web/src/features/conversation/content/parts/DataBackgroundTaskStarted.test.tsx`
- `apps/web/src/features/conversation/content/parts/DataTaskProgress.tsx`
- `apps/web/src/features/conversation/content/parts/ToolApprovalControls.tsx`
- `apps/web/src/features/conversation/content/parts/ToolApprovalControls.test.tsx`
- `apps/web/src/features/conversation/content/parts/ToolThink.tsx`
- `apps/web/src/features/conversation/content/ModelBadge.tsx`
- `apps/web/src/features/conversation/content/dataPartDispatch.test.tsx`
- `apps/web/src/features/conversation/content/parts/SubAgentCallCard.test.tsx`
- `apps/web/src/lib/utils/usageFormat.ts` and `usageFormat.test.ts`
- `apps/web/src/lib/utils/toolNames.ts`
- `apps/web/src/lib/models/phaseRoles.ts` and `phaseRoles.test.ts`

**Delete**

- `apps/web/src/features/conversation/content/parts/SubAgentCallCard.tsx`

### Interfaces

**Consumes** from batch 1:

```ts
import {
  buildTrace,
  type Trace,
  type TraceGroup,
  type TraceRow,
  type TraceRowStatus,
} from "@pathfinder/assistant-client";
```

**Produces**, consumed by Implementer B:

```ts
// lib/components/thread/Trace.tsx
export function Trace(props: {
  run: TraceRunView;
  showRaw: boolean;
  showUsage: boolean;
  labelFor?: (phase: string) => string;
  nameFor: (toolName: string) => string;
  approval?: ReactNode;
}): ReactElement;

export interface TraceRunView {
  groups: TraceGroup[];
  rowCount: number;
  running: boolean;
}

// lib/components/thread/TaskRow.tsx
export function TaskRow(props: {
  label: string;
  percent: number | null;
  message: string | null;
  estimatedSeconds: number | null;
  outcome: "running" | "success" | "failure";
  error: string | null;
}): ReactElement;

// lib/components/thread/ApprovalCard.tsx
export function ApprovalCard(props: {
  title: string;
  input: unknown;
  showRaw: boolean;
  onApprove: () => void;
  onDeny: () => void;
  decision: "pending" | "approved" | "denied";
}): ReactElement;

// features/conversation/thread/traceRenderingKinds.ts
export const TRACE_RENDERING_KINDS: ReadonlySet<string>;

// features/conversation/thread/useThreadDevMode.ts
export function useThreadDevMode(): { showRaw: boolean; showUsage: boolean };
```

`nameFor` is injected because `humanizeToolName` names PathFinder's tools;
`TraceAnchor` passes it. `labelFor` is an OPTIONAL override for a host that
names phases differently. Its default is the one label set,
`PHASE_LABELS` in `apps/web/src/lib/models/phaseRoles.ts`, which `TraceGroup`
imports directly - `@/lib/models/` is `@/lib`, so the boundary rule allows it,
and one shared map beats a second copy inside the component.
`TraceAnchor` passes no `labelFor`.

### The UX specification, concretely

**Lead rulings at close, where the batch as executed departs from the text
below (the frozen suites and the repo gates decided each one):**

- `data-testid="turn-trace"` is the OUTER wrapper of the whole trace block
  (toggle, summary, rows, approval), because the frozen e2e journey scopes
  `turn-trace-summary` and `turn-trace-toggle` inside
  `[data-testid="turn-trace"]:has([data-testid="trace-row"])`. The collapsing
  grid container carries no testid.
- The collapse keeps the rows `visibility: hidden` once closed, applied after
  the 300 ms transition ends (`onTransitionEnd`), never at the start of it.
- The group usage text is `text-muted-foreground` with NO alpha:
  `statusTokens.test.ts` forbids an alpha-faded status or muted text token
  anywhere in source, and the gate wins over the class written below.
- Every data renderer's own testid is passed to `Figure` as `testId`, which
  puts it on one `<div>` inside the `<figure>` that wraps the figcaption, the
  body and the caption together, so a title in the figcaption is inside the
  identified element (the frozen EDA journey asserts the study title inside
  `data-eda-analysis-state`) while the `<figure>` keeps `data-testid="figure"`
  (the frozen figures module counts figures and looks the part up within
  one). Child testids keep their elements.
- `ModelBadge` separates with an ASCII `-`, not U+00B7.
- `TraceAnchor` narrows `data-sub-agent-call` and `data-tool-summary` payloads
  with the generated zod schemas in `packages/shared-ts/src/generated/zod/`,
  never by hand.
- `traceRenderingKinds()` is a function, not a module-level const: a real ESM
  cycle (`coreDataParts -> TraceAnchor -> traceRenderingKinds ->
  contentComponents -> coreDataParts`) makes an eager const throw at import.
- Paired testids nest rather than share one element (`tool-call-part` wraps
  `trace-row`, `data-sub-agent-call` wraps `trace-group`, `data-task-completed`
  wraps `task-row`).

**`Trace`** renders, in order:

- A header button, `data-testid="turn-trace-toggle"`, full width, `h-7`,
  `text-xs text-muted-foreground hover:text-foreground`, no border, no
  background. It holds a chevron (`lucide-react` `ChevronRight`, `size-3`,
  rotated 90 degrees when open) and one label,
  `data-testid="turn-trace-summary"`:
  - `Working...` while a row is `running`; `Waiting for you` while no row
    runs and one is `awaiting-approval` (lead ruling after the first real
    turn: a consult question is the user's move, not the assistant's work)
  - `1 step` when `rowCount === 1`
  - `` `${rowCount} steps` `` otherwise
- The rows container, `data-testid="turn-trace"`, a `grid` whose
  `gridTemplateRows` animates `0fr` to `1fr` over 300 ms
  `cubic-bezier(0.23, 1, 0.32, 1)`, with `overflow-hidden` on the inner div.
  This is the Beautiful UI collapse; it needs no library.
- **Open by default while `run.running` is true, closed once it settles**,
  with a manual override that wins:
  `const open = manual ?? run.running;` and `manual` is `useState<boolean |
  null>(null)`. A reader watches the work and then it gets out of the way.
- One `TraceGroup` per group.
- `props.approval` last, when given.

**`TraceGroup`** renders a group. When `phase` is `"lead"` and it is the only
group, it renders its rows bare, with no label: a turn the Lead did alone needs
no heading. Otherwise:

- A label row, `data-testid="trace-group"`, `h-6`, with
  `data-testid="trace-group-label"` carrying `labelFor(phase)` in
  `text-[11px] font-medium uppercase tracking-wide text-muted-foreground`, and,
  when `showUsage` is true and `tokens > 0`,
  `data-testid="trace-group-usage"` carrying `formatUsage(tokens, costUsd)` in
  `text-[11px] text-muted-foreground/70`. With `tokens` 12300 and `costUsd`
  `"0.004"` that reads exactly `12.3K, $0.004`.
- Its rows, indented by a `pl-3 border-l border-border/50` rail. The rail is
  the only line the trace draws.

**`TraceRow`** is one line, `data-testid="trace-row"`, `h-6`, `flex
items-center gap-2 text-xs`:

- The glyph, `data-testid="trace-row-status"`, `size-3`, from
  `traceGlyphs.tsx`, one per `TraceRowStatus`:

  | status | glyph | class |
  |---|---|---|
  | `running` | `Loader2` spinning | `text-muted-foreground animate-spin` |
  | `ok` | `Check` | `text-success` |
  | `empty` | `CircleSlash` | `text-warning` |
  | `warn` | `TriangleAlert` | `text-warning` |
  | `error` | `X` | `text-destructive` |
  | `denied` | `Ban` | `text-muted-foreground` |
  | `awaiting-approval` | `ShieldAlert` | `text-warning` |

  `empty` is a distinct glyph on purpose. A call that found nothing and a call
  that found something must not look the same; that is the silent zero.
- The verb, `nameFor(toolName)`, `text-foreground/80`, never truncated.
- The summary, `data-testid="trace-row-summary"`,
  `text-muted-foreground truncate`, or the error text when `status` is
  `error`, truncated to 120 characters on a word boundary with an ASCII `...`.
- When `showRaw` is true, a chevron button that reveals
  `data-testid="trace-row-raw"`: the existing ai-elements `ToolInput` and
  `ToolOutput`, unchanged, in a `pl-5 py-1` block. This is the only place JSON
  appears in the whole thread.
- The row carries `data-testid="tool-call-part"` as a SECOND testid on the same
  element, and the `think` row also carries `data-testid="tool-think"`. Both
  testids survive on the element that now IS the tool call part.

**`TaskRow`**, `data-testid="task-row"`, `h-8`, `flex items-center gap-2`:

- A status badge, `size-5`: a ring that sweeps to `percent` while running, a
  `Check` in `text-success` on success, an `X` in `text-destructive` on
  failure.
- The label, truncated, `text-[13px]`. It is
  `humanizeToolName(<the tool_name the wire carries>)`. The enrichment task
  puts `geneset_enrichment` on the wire
  (`apps/api/src/pathfinder/ai/tools/standalone/workbench.py` line 146), so
  `apps/web/src/lib/utils/toolNames.ts` gains the entry
  `geneset_enrichment: "Gene set enrichment"` and the row reads
  `Gene set enrichment`. The existing `run_gene_set_enrichment` entry is the
  agent-side name and stays.
- The amount, right-aligned, `text-xs text-muted-foreground`,
  `data-testid="task-row-status"`: `` `${Math.round(percent * 100)}%` `` while
  running, `Completed` on success, `Failed` on failure.
- When `estimatedSeconds` is not null and the task is running,
  `data-testid="task-row-elapsed"` reading `` `~${estimatedSeconds} s` ``.
- The progress bar keeps `data-testid="data-task-progress"` on its container
  and `data-testid="progress-bar-fill"` on its fill, because both are asserted
  today. Its color becomes `bg-primary`, not the hardcoded `bg-blue-500` that
  is there now.
- On failure, the error text under the row, `text-xs text-destructive`.

**`ApprovalCard`**, `data-testid="approval-card"`, is the ONE place the thread
still draws a bordered box, because the user must act:
`rounded-md border border-warning/40 bg-warning/10 p-3`.

- `data-testid="approval-card-title"` reads the whole `prompt` its caller
  passed. `approvalPromptFor` writes it: `` `${label} needs your approval
  before it runs.` `` for every tool but the destructive ones, which name what
  they destroy.
- The input, only when `showRaw` is true. Today it is always shown; that is the
  JSON the calm default removes.
- Buttons `Deny` (`variant="outline"`, `data-testid="tool-approval-deny"`) and
  `Approve` (`data-testid="tool-approval-approve"`), unchanged copy.
- Resolved: one line, `data-testid="tool-approval-decision"`, reading
  `Approved` or `Denied`, unchanged.

### Task A1: `TraceRow` and the glyphs

Red: `TraceRow.test.tsx`. Seven cases, one per `TraceRowStatus`, each asserting
the glyph's testid, its class, the verb and the summary text. Then the truncation
case: a 200-character error truncates to 120 on a word boundary and ends in
`...`. Then the two raw cases: `showRaw` false yields zero `trace-row-raw`
elements AND `container.textContent` contains no `{`; `showRaw` true yields one
and the input's keys appear.

Green: `TraceRow.tsx` plus `traceGlyphs.tsx`. `traceGlyphs.tsx` is a
`Record<TraceRowStatus, {icon, className}>` with a `switch`-free lookup, so
`switch-exhaustiveness-check` has nothing to complain about and adding a status
to the union fails the type check.

### Task A2: `TraceGroup` and `Trace`

Red: `Trace.test.tsx`.

1. `rowCount` 1 yields `1 step`; 7 yields `7 steps`; `running` true yields
   `Working...`.
2. `running` true renders the rows visible without a click; `running` false
   renders them hidden; clicking `turn-trace-toggle` flips either.
3. A single `lead` group renders NO `trace-group-label`.
4. Three groups render labels `Lead`, `Frame`, `Lead` through the shared
   `PHASE_LABELS`, and a group whose phase is `build` renders `Build`.
5. `showUsage` false renders zero `trace-group-usage`; true with `tokens` 12300
   and `costUsd` `"0.004"` renders exactly `12.3K, $0.004`
   (overview section 7).
6. `props.approval` renders after the last group.

Green: `TraceGroup.tsx` and `Trace.tsx`. Keep each under 120 lines.

`formatUsage` separates with U+00B7 today, which breaks the ASCII rule the
moment a test pins its output. In this task `apps/web/src/lib/utils/usageFormat.ts`
and `usageFormat.test.ts` change to the ASCII form: a comma and a space, so
`formatUsage(12300, "0.004")` is `12.3K, $0.004`. `formatCost` keeps its
two-decimal rule at or above one cent, so `formatUsage(41800, "0.0131")` is
`41.8K, $0.01`. The function's doc comment moves to the comma form with it.
Every consumer - `TraceGroup` and `ModelBadge` - is re-pinned in the same task.

### Task A3: `TaskRow`, and `DataBackgroundTaskStarted` rewired

Red: `TaskRow.test.tsx` for the component, then
`DataBackgroundTaskStarted.test.tsx` extended: the existing suite already
drives the started, progress and completed sequence off `chat.messages`; assert
it now renders `task-row` with `Completed`, that `progress-bar-fill` survives,
and that `container.textContent` contains no `{`.

Green: `TaskRow.tsx`, and `DataBackgroundTaskStarted.tsx` reduced to the
derivation it already does plus a `<TaskRow>`. Its own card chrome and its
`humanizeToolName` call stay; only the presentation moves. `DataTaskProgress.tsx`
becomes the bar `TaskRow` renders, exported from `lib/components/thread/`, and
its `bg-blue-500` is replaced by `bg-primary` in this task, not left for batch 3.
The registry entries for `data-task-progress` and `data-task-completed` stay
`() => null`; the negative assertions in `dataPartDispatch.test.tsx` must still
pass.

### Task A4: `ApprovalCard`, and `ToolApprovalControls` rewired

Red: `ApprovalCard.test.tsx` for the component; then
`ToolApprovalControls.test.tsx`, 217 lines today, extended so that its pending
case asserts `approval-card` and its input is ABSENT with `showRaw` false and
PRESENT with `showRaw` true, and its resolved case still asserts
`tool-approval-decision`.

Green: `ApprovalCard.tsx`, and `ToolApprovalControls.tsx` keeps
`findToolApproval` and the `chat.addToolApprovalResponse` call and renders
`<ApprovalCard>`. Its `consult_user` exclusion stays: `ConsultCarousel` owns
that approval and this batch does not touch it.

`Trace` receives the card through its `approval` prop, so it lands at the end
of the run rather than in the middle of the rows.

### Task A5: `TraceAnchor` and `MessageRenderer`

Red: `TraceAnchor.test.tsx`.

1. Given a message whose parts are batch 0's recorded turn, rendering the
   anchor for `call_1` yields the whole trace; rendering it for `call_2`,
   `call_3`, `call_4`, `call_5`, `s1` or `s2` yields an empty container.
2. Rendering the anchor for a `data-sub-agent-call` part that is not its run's
   first element yields an empty container.
3. With no `ChatHelpersProvider`, the anchor renders exactly one `trace-row`
   for its own part, carrying `tool-call-part`.
4. The rendering kinds are excluded from the rows: no `trace-row` names
   `data-eda.viz`.

Green:

- `traceRenderingKinds.ts` is the explicit set, and it is derived from
  `dataPartComponents` rather than hand-listed: the rendering kinds are exactly
  the kinds whose component is not one shared no-render function. Today the
  eight non-drawing entries (seven in `coreDataParts.ts`, `data-ledger-update`
  in `strategyDataParts.ts`) are separate inline `() => null` arrows, and the
  only named `noRender` lives in `dataPartRegistry.ts`. Export one `noRender`
  from `coreDataParts.ts`, point all eight entries and `dataPartRegistry.ts`
  at it, so the derivation is an identity check and cannot drift.
  Three kinds are then SUBTRACTED explicitly: `data-turn-failed` and
  `data-turn-stopped` draw, but they are turn-level notices the message
  renders, not figures a run produced, so hoisting them would move a failure
  notice into the trace's figure list; and `data-background-task-started`
  draws as a `TaskRow` inside the trace, not as a figure. The set names the
  exclusion in one line and `TraceAnchor.test.tsx` asserts that a
  `data-turn-failed` part yields no figure and that a task part yields no
  figure either.
- `useThreadDevMode.ts` reads `showRawToolCalls` and `showTokenUsage` from
  `useSettingsStore` and returns them as `showRaw` and `showUsage`. It is the
  only reader of those flags in the thread.
- `TraceAnchor.tsx` does the anchoring described above.
- `MessageRenderer.tsx`: `ToolCall` is deleted; `tools.Fallback` and
  `tools.by_name.think` both become `TraceAnchor`. `toolUIState` stays, because
  `MessageRenderer.test.tsx` pins its five mappings and the anchor needs it to
  build a row in degraded mode.
- `coreDataParts.ts`: `data-sub-agent-call` maps to `TraceAnchor`.
- `ModelBadge.tsx` returns null when `showUsage` is false.
- `SubAgentCallCard.tsx` is DELETED. `SubAgentCallCard.test.tsx` is rewritten
  as a `TraceGroup` test asserting the same behaviors: the phase label, the
  usage chip, the state dot, and the nested steps. `MessageRenderer.test.tsx`'s
  `data-sub-agent-call` assertion moves onto the group element, which now
  carries that testid.
- `SubAgentCallCard`'s private `PHASE_LABELS` is deleted with the file. ONE
  label set remains, in `apps/web/src/lib/models/phaseRoles.ts`, and it is:

  ```
  lead: "Lead"
  frame: "Frame"
  build: "Build"
  execution: "Build"                 // alias, for logs recorded before
                                     // batch 1 unified the wire
  verification: "Verification"
  recover_failed_steps: "Recovery"
  ```

  `build` is the phase `_lead_events.py`'s `_SUB_AGENT_TOOL_TO_PHASE` puts on
  the wire for `build_strategy` and `recover_failed_steps`, and batch 1 makes
  `sub_agent_stream.py` emit the same names. `PHASE_LABELS` is therefore keyed
  by the wire's phase strings, not by `PhaseRole`, so its type widens from
  `Record<PhaseRole, string>` to `Record<string, string>`. `PHASE_ROLES`,
  `PhaseRole` and `PHASE_DESCRIPTIONS` are untouched, and every `PhaseRole`
  still has an entry, so `ModelSettings.tsx` line 114's `PHASE_LABELS[role]`
  keeps rendering a label. Confirm that with its test, not by reading it.
  `phaseRoles.test.ts`'s `toBeTruthy` becomes an assertion on the six values.
  `TraceGroup` imports this map as its default `labelFor`.

## Implementer B: the figures

### Files

**Create**

- `apps/web/src/lib/components/thread/Figure.tsx`
- `apps/web/src/lib/components/thread/Figure.test.tsx`

**Modify** (every renderer that draws)

- `content/parts/DataEdaAnalysisState.tsx`, `DataEdaSubsetPreview.tsx`,
  `DataEdaViz.tsx`, `DataEnrichmentResults.tsx`, `DataVariantComparison.tsx`,
  `DataScoredComparison.tsx`, `DataVerificationSummary.tsx`, `DataGeneSet.tsx`,
  `DataStrategyLink.tsx`, `DataStrategyMeta.tsx`, `DataGraphSnapshot.tsx`,
  `DataGraphCleared.tsx`, `DataMemoryRetrieved.tsx`,
  `DataConversationTitle.tsx`
- their existing `.test.tsx` siblings
- `content/FailureNotice.tsx`, `content/StoppedNotice.tsx`
- `content/AssistantThinkingPlaceholder.tsx`
- `content/SupersededBadge.tsx`

### Interfaces

```ts
// lib/components/thread/Figure.tsx
export function Figure(props: {
  title: string | null;
  caption: string | null;
  children: ReactNode;
  testId?: string;
}): ReactElement;
```

`Figure` renders:

```
<figure data-testid="figure" className="my-6 border-t border-border/60 pt-4">
  {title  && <figcaption className="mb-2 text-sm font-medium">{title}</figcaption>}
  {children}
  {caption && <div data-testid="figure-caption"
                   className="mt-2 text-xs text-muted-foreground">{caption}</div>}
</figure>
```

No border, no rounded corner, no card background, no shadow. That class list is
the contract batch 0 task 0.4 item 5 asserts.

### The restyle table

Each renderer keeps its own testid on the element it is on today, keeps every
child testid, and wraps its body in `<Figure>`. The title and the caption are
fixed here so two implementers cannot disagree, and the caption carries the
numbers.

| renderer | title | caption |
|---|---|---|
| `DataEdaAnalysisState` | `analysis.studyDisplayName` | one clause per `entityCounts` entry, `` `${count.toLocaleString()} of ${unfilteredCount.toLocaleString()} ${entityDisplayName}` ``, joined by `", "`, the display name as the wire gives it: `6 of 12 Sample, 34,320 of 68,640 pfal3D7 htseq counts` for the recorded turn |
| `DataEdaSubsetPreview` | `distribution.variableDisplayName` | the same joined clause over its own `entityCounts`, then `` `, ${numVarValues.toLocaleString()} values` ``: `6 of 12 Sample, 6 values` for the recorded turn |
| `DataEdaViz` | `effectSizeLabel` | `` `${retainedPoints.toLocaleString()} of ${totalPoints.toLocaleString()} genes retained` `` - `1,543 of 5,511 genes retained` |
| `DataEnrichmentResults` | `Enrichment` | `` `${n} terms, ${genes} genes analyzed` `` |
| `DataVariantComparison` | `Variants` | `` `${n} variants, ${best} genes in the largest` `` |
| `DataScoredComparison` | `Scored variants` | `` `${n} variants, winner ${winner} at ${score}` `` |
| `DataVerificationSummary` | `Verification` | `` `${passed} of ${total} checks passed` `` |
| `DataGeneSet` | `name` | `` `${geneCount.toLocaleString()} genes on ${siteId}` `` |
| `DataStrategyLink` | `Strategy` | the strategy name; the `<a>` and its accessible name are unchanged, because `MessageRenderer.test.tsx` asserts `role="link"` named `Test` |
| `DataStrategyMeta` | none | `` `${name} - ${geneCount.toLocaleString()} genes${saved ? ", saved" : ""}` `` |
| `DataGraphSnapshot` | none | `` `${steps} steps, ${genes.toLocaleString()} genes` `` |
| `DataGraphCleared` | none | `` `Strategy cleared - ${reason}` `` |
| `DataMemoryRetrieved` | `Recalled memories` | `` `${n} memories` `` |
| `DataConversationTitle` | (lead ruling after the first real turn: draws nothing; the title already reaches the sidebar through `useChatRuntime`, and a one-line figure with a rule and 24 px margins for it was the first thing a reader saw) | |

The last four have no chart and no table; they render as a caption line alone,
with `title` null and no `figcaption`. A pill with a border is not a figure, and
they stop being pills.

`FailureNotice`, `StoppedNotice`, `AssistantThinkingPlaceholder` and
`SupersededBadge` are NOT figures: they are turn-level notices and keep their
current placement in `AssistantMessage`. They lose their card chrome in the
same way - hairline and text, no border - and `SupersededBadge`'s hardcoded
`border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400` at
line 67 becomes the `--warning` token in THIS task, not in batch 3.
`LedgerContrasts.tsx` lines 31 and 35 (`text-amber-600`, `text-amber-600/80`)
are the rail, not the thread; batch 3 owns them.

### Task B1: `Figure`

Red: `Figure.test.tsx`. Title present and absent, caption present and absent,
the class contract asserted exactly as batch 0 asserts it, and children
rendered.

Green: `Figure.tsx`, under 40 lines.

### Task B2: the fourteen renderers

One test edit and one component edit per renderer, in the order of the table.
For each, the existing test file gains a caption assertion with the real
numbers, and loses any assertion on a border class. The five renderers with no
test file today (`DataEnrichmentResults`, `DataVariantComparison`,
`DataStrategyMeta`, `DataGraphSnapshot`, `DataGraphCleared`) gain one; a
renderer without a test cannot prove its caption.

The EDA three are the sharp ones, because the frozen suites assert them:

- `DataEdaSubsetPreview` must still expose `data-eda-subset-bin-1`,
  `data-eda-subset-coverage`, `data-eda-subset-multivalued`,
  `data-eda-subset-note` and `data-eda-subset-histogram`.
- `DataEdaViz` must still expose `data-eda-viz`, `data-eda-viz-empty`,
  `data-eda-viz-unsupported-chart`, `eda-viz-volcano` with `role="img"`,
  `eda-viz-volcano-selection`, `eda-viz-volcano-genes`,
  `eda-viz-volcano-dropped`, `eda-viz-scatter` and `eda-viz-scatter-count`.
- `DataEdaAnalysisState` must still expose `data-eda-analysis-state`,
  `data-eda-filter-chip-0` and `data-eda-filter-overflow`, and its
  "Open in EDA tab" button.

Run `npx vitest run --config vitest.acceptance.config.ts` after each of the
three, not once at the end. The frozen EDA modules are the fastest signal that
a testid moved.

### Task B3: the borders come off

A sweep, done last, with a named list rather than a grep-and-hope:

- `content/parts/*` - every `rounded-lg border bg-card` and every
  `rounded-md border` on a renderer's outer element is deleted. `ApprovalCard`
  is the sole exception and it is Implementer A's.
- `components/ai-elements/tool.tsx` - `Tool` is now unused by the thread.
  Confirm with `findReferences` before touching it: it is still used by
  `TraceRow`'s raw disclosure through `ToolInput` and `ToolOutput`. Delete
  `Tool`, `ToolHeader` and `ToolContent` only if nothing references them, and
  update `components/ai-elements/tool.test.tsx` in the same edit.
- `MessageContent` in `components/ai-elements/message.tsx` carries an
  `is-user:dark` class that has no effect today. Leave it; batch 3 owns it.

## Section close-outs

**A:**

- [ ] `cd apps/web && yarn format`
- [ ] `npx tsc --noEmit && npx eslint src/ && node scripts/check-boundaries.mjs && node scripts/check-weak-assertions.mjs && npx vitest run`
- [ ] `npx vitest run --config vitest.acceptance.config.ts` - report thread
  modules passing and EDA modules passing, unmodified.
- [ ] Report: every file over 200 lines with its count; the exact anchoring
  predicate `TraceAnchor` uses, quoted; where `PHASE_LABELS` now lives and
  every consumer; zero-debt statement or the debt.

**B:**

- [ ] same ladder
- [ ] `THREAD_ACCEPTANCE=1 npx playwright test --project=thread-acceptance`
- [ ] Report: each of the fourteen renderers with its caption string and the
  test that asserts it; every testid from [overview.md](overview.md) section 6
  with the file and element that now carries it, or MISSING; zero-debt
  statement or the debt.

## Verifier

Re-run:

```
cd /Users/ahmedmuharram/repos/pathfinder/apps/web
yarn install --immutable
npx tsc --noEmit
npx eslint src/
node scripts/check-boundaries.mjs
node scripts/check-weak-assertions.mjs
npx vitest run
npx vitest run --config vitest.acceptance.config.ts
EDA_ACCEPTANCE=1 npx playwright test --project=eda-acceptance
THREAD_ACCEPTANCE=1 npx playwright test --project=thread-acceptance
node /Users/ahmedmuharram/repos/pathfinder/scripts/check-knowledge.mjs
```

Traps, by name:

1. **JSON in the calm default.** Render the recorded turn with both flags at
   their defaults and grep `container.textContent` for `{`, `datasetId`,
   `wdkStepId`. One hit is a FAIL, and it is the whole point of the batch.
2. **`showRawToolCalls` read anywhere but `useThreadDevMode`.** Grep.
3. **`showTokenUsage` read anywhere but `useThreadDevMode`.** Grep.
4. **A third settings flag added.**
5. **A `useEffect`, `useMemo`, `useCallback` or `memo`** anywhere in the diff.
6. **`@/features/*` or `@/state/*` imported from `lib/components/thread/`.**
   This is what makes the components liftable; a single import kills it.
7. **A new entry in `CROSS_FEATURE_EXCEPTIONS`.** Reject outright.
8. **A component calling `fetch`.**
9. **A missing testid.** Walk [overview.md](overview.md) section 6 item by
   item against the rendered DOM of the recorded turn, not against a grep of
   the source: a testid in a dead branch is not a surviving testid.
10. **`data-task-progress` or `data-task-completed` rendering a standalone
    card.** `dataPartDispatch.test.tsx` asserts the negative; confirm it still
    runs.
11. **The trace open by default after a turn settles.** It must collapse.
12. **The trace collapsed while running.** A reader must see the work happen.
13. **A `Figure` with a border.** Assert the class contract on all fourteen.
14. **A caption without its numbers.** A caption reading `Subset preview` is a
    label, not a caption. Name any that fail.
15. **A `.toLocaleString()` missing** on a count over 999. `34,320` and
    `68,640` and `5,511` and `1,543` all appear in the acceptance suite.
16. **`SubAgentCallCard.tsx` still present**, or its logic copied rather than
    replaced.
17. **`mergeSubAgentSteps` re-implemented** in `apps/web` instead of imported
    from the client package.
18. **`humanizeToolName` or `PHASE_LABELS` imported into
    `lib/components/thread/`** rather than injected.
19. **A file over 300 eslint-counted lines**, or a silenced `max-lines`.
20. **Smart punctuation** in any new source file.
21. **A weak assertion.** Read `check-weak-assertions.mjs`'s output.
22. **A frozen file modified.** `diff -r` first, before anything else.
23. **`bg-blue-500` still in `DataTaskProgress`**, or a new hardcoded color
    anywhere in `features/conversation/**`.
24. **The degraded mode dropped.** Render a tool part with no
    `ChatHelpersProvider` and confirm one row, not a crash and not an empty
    container.

Mutation probes, three:

- In `Trace.tsx`, invert the default-open expression (`manual ?? !run.running`).
  A test must fail.
- In `TraceRow.tsx`, render `status: "empty"` with the `ok` glyph. A test must
  fail on the class or the testid, not merely on a snapshot.
- In `DataEdaViz.tsx`, swap `retainedPoints` and `totalPoints` in the caption.
  A test must fail asserting `1,543 of 5,511`.

Report format, mandatory:

```
Batch 2 verification

Gates
  tsc --noEmit                  PASS/FAIL  <first error if FAIL>
  eslint src/                   PASS/FAIL  <count>
  check-boundaries.mjs          PASS/FAIL  <count>
  check-weak-assertions.mjs     PASS/FAIL  <count>
  vitest run                    PASS/FAIL  <passed>/<total>, <duration>
  vitest acceptance config      PASS/FAIL  thread <n>, eda <n>
  playwright eda-acceptance     PASS/FAIL
  playwright thread-acceptance  PASS/FAIL
  check-knowledge.mjs           PASS/FAIL

Acceptance no-edit check        PASS/FAIL  <diff -r output>

Per task
  A1 TraceRow + glyphs      PASS/FAIL  <evidence>
  A2 TraceGroup + Trace     PASS/FAIL
  A3 TaskRow                PASS/FAIL
  A4 ApprovalCard           PASS/FAIL
  A5 TraceAnchor + renderer PASS/FAIL
  B1 Figure                 PASS/FAIL
  B2 fourteen renderers     PASS/FAIL  <n>/14
  B3 borders off            PASS/FAIL

Testids  (every entry of overview section 6: file:element, or MISSING)

Captions  (each of the fourteen: the string rendered, the test that asserts it)

Traps  (1 to 24, each CLEAN or the file:line that violates it)

Mutation probes  (each: the mutation, the killing test, or SURVIVED)

Definition of done
  zero debt            YES/NO  <what remains>
  adjacent reconciled  YES/NO  <what was missed>
  tests assert values  YES/NO
```

## Exit criteria

For the session lead to close batch 2:

1. Every gate green, verified by the lead's own run.
2. The recorded turn renders with two traces, seven rows, three group labels,
   three figures, one task row and one approval card, and no JSON in the DOM.
3. `showRawToolCalls` on reveals raw input and output under every row and
   nowhere else; off leaves none in the DOM.
4. `showTokenUsage` off removes `model-badge` and every `trace-group-usage`;
   on restores both. The default stays `true`.
5. The trace is open while the turn runs and collapsed to `N steps` when it
   settles, with a manual toggle that wins in both directions.
6. All fourteen figures render without a border and with a caption carrying
   real numbers.
7. `SubAgentCallCard.tsx` is deleted and nothing reimplements it.
8. Every testid in [overview.md](overview.md) section 6 is present in the
   rendered DOM of the recorded turn.
9. The frozen EDA vitest modules and the frozen EDA e2e journey pass
   unmodified, and the thread acceptance modules pass unmodified.
10. The verifier's report shows all twenty-four traps CLEAN, three mutation
    probes killed, and "zero debt YES".
