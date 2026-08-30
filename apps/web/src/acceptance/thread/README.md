# Thread acceptance suite (frontend)

Behavior-only conformance tests for the thread redesign, written from
`docs/knowledge/thread/plan/overview.md`'s pinned contract and from values
recorded in this repo, before any of the implementation exists.

**No-edit rule.** Implementers may not touch `src/acceptance/**`,
`e2e/acceptance/**`, `vitest.acceptance.config.ts` or the `eda-acceptance` and
`thread-acceptance` projects in `playwright.config.ts`. A wrong test is
escalated to the session lead, the only party who edits the suite.

**Run it:** `yarn vitest run --config vitest.acceptance.config.ts` (the default
run never collects `*.acceptance.tsx`).

## The files

- `recordedTurn.json` - one assistant turn as a protocol chunk array, in wire
  order. The EDA payloads are the values of
  `features/conversation/content/parts/edaPartFixtures.ts`, copied in rather
  than imported, because an implementer may edit that file. The volcano part
  carries the live-verified compute totals, `totalPoints` 5511 and
  `retainedPoints` 1543, over the three-point fixture. The task id and
  `run_control_tests_on_step` come from `e2e/feature/durable-verification.spec.ts`.
  It is the artifact the other three modules read.
- `support.ts` - `loadOrSkip`, the recorded chunks, and `renderTurn`, which
  reduces a chunk array through `reduceSnapshot` and renders the resulting
  message through the thread's own `AssistantMessage`, inside a
  `ChatHelpersProvider` whose `messages` carry the same reduced parts.
- `calm-default.acceptance.tsx` - the reading surface with both flags at their
  defaults.
- `dev-mode.acceptance.tsx` - the same turn under `showRawToolCalls` and
  `showTokenUsage`.
- `figures.acceptance.tsx` - the three figures, their captions and their class
  contract.

## `loadOrSkip` takes a specifier, not a thunk

The batch document allowed either form. This suite takes the specifier string,
the same as `acceptance/eda/support.ts`, because a thunk keeps the path
statically analysable and Vite then refuses to transform a module whose dynamic
import cannot be resolved. A missing batch-2 module would become a collection
error instead of a skip, which is the one thing the guard exists to prevent.
With a string, the import is unanalysable, the rejection is catchable, and the
module skips.

## What skips today, and on what

Each module opens with one guarded import and calls `describe.skipIf` on it.
All three target components batch 2 creates, so all three skip until it lands:

| module                        | gated on                                          |
| ----------------------------- | ------------------------------------------------- |
| `calm-default.acceptance.tsx` | `@/lib/components/thread/Trace`                   |
| `dev-mode.acceptance.tsx`     | `@/features/conversation/thread/useThreadDevMode` |
| `figures.acceptance.tsx`      | `@/lib/components/thread/Figure`                  |

Nothing here runs green against today's code. Every assertion pins new
behavior: the trace and its rows, the task row, the approval card, the figure
captions, and the ASCII comma form of `formatUsage`. Two assertions touch parts
that already draw - the EDA filter chip and the subset coverage line - and they
are there so the restyle cannot move what the frozen EDA suite pins; they stay
inside the gated describe, because the elements only reach the DOM through the
new renderer.

## The one styling assertion

`figures.acceptance.tsx` asserts that no element carrying
`data-testid="figure"` has a `border`, `rounded-lg`, `rounded-md` or
`shadow-card` class and that every one has `border-t`. It compares class
TOKENS, not a regular expression, because `\bborder\b` also matches inside
`border-t` and would refuse the very class the contract requires. Every other
assertion in this suite is on text, counts, testids or DOM order.

## Where this suite reads the batch card differently

Three assertions do not match `batch-0-acceptance-layer.md` task 0.2 literally,
because the card's own numbers contradict the contract in
[overview.md](../../../../../docs/knowledge/thread/plan/overview.md). Each is
resolved toward the contract, which the card calls law.

1. **One `turn-trace`, not two.** The recorded turn's parts hold exactly one run
   that bears rows: the first text part precedes every tool part, and the only
   part after the second text part is `data-lead-usage`, which rule 9 says never
   opens a run. Batch 2 renders a trace at a run's first row-bearing part, so a
   run with zero rows draws nothing. `buildTrace` may still report two runs; the
   document holds one `turn-trace`.
2. **`Working...`, then `7 steps`.** Overview section 2 makes `running` true
   when a row is `awaiting-approval`, and `call_5` is, so the recorded turn's
   label is `Working...`. The `7 steps` literal is pinned by a second case that
   drives `SETTLED_CHUNKS`: the same turn plus the approval continuation of
   PROTOCOL section 6.2, where the sweep returns and nothing waits on the user.
   Both literals are asserted; neither is asserted of the wrong turn.
3. **The figure class check compares tokens**, for the reason above.

## The theme test and the other two halves

`theme.acceptance.ts` reads `src/styles/globals.css` and
`src/lib/components/charts/chartTheme.ts` as text, the way
`styles/statusTokens.test.ts` does. It skips until batch 3 adds the
`:root[data-theme="dark"]` block, then asserts that every color token on bare
`:root` has a dark value and none is dark-only, that `.dark` is gone, that
`@custom-variant dark` names the attribute, and that no color is defined
inside a media query.

The protocol half of this suite lives in
`packages/assistant-client-ts/tests/acceptance/thread/` (`yarn test:acceptance`)
and the page journey in `e2e/acceptance/thread-journeys.spec.ts`
(`THREAD_ACCEPTANCE=1 yarn playwright test --project=thread-acceptance`).
