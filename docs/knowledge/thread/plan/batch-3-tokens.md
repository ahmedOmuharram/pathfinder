---
type: Plan
title: "Batch 3: tokens and palette"
description: One token layer with a light and a dark value for every color, the chart set included, the dark utilities rebound to a data-theme attribute PathFinder never sets, per-site brand injection made ground-aware, and every hardcoded color in the app migrated onto the tokens.
tags: [thread, pathfinder, plan, batch, frontend, design, tokens, charts, theme]
generated: { by: claude-code/opus-5, at: 2026-08-29T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-29T00:00:00Z }
status: accepted
---

# Batch 3: tokens and palette

**Goal:** every color in the app comes from a token, every token has a light
value and a dark value, and the eight chart tokens are validated against both
grounds. PathFinder still ships light; it just no longer has a half-built dark
mode that fires on a stranger's operating system.

**Prerequisites:** batch 2 closed. The thread's own hardcoded colors
(`DataTaskProgress`'s `bg-blue-500`, `SupersededBadge`'s amber) were already
fixed there; this batch owns everything else.

**This batch closed** the backlog item `chart-tokens-have-no-dark-mode-values`
(deleted, with its index line, when the work finished).

**Read before starting:**

- [overview.md](overview.md) section 4 - the theme rule is law.
- [batch-0-acceptance-layer.md](batch-0-acceptance-layer.md) task 0.7 - the
  eight assertions this batch must satisfy, frozen.
- `apps/web/src/styles/globals.css` in full, all 793 lines.
- `apps/web/src/styles/statusTokens.test.ts` in full. Its regex takes the FIRST
  `--token: H S% L%;` match in the file, and it throws on any value that is not
  an `H S% L%` triple.
- `apps/web/src/lib/components/charts/chartTheme.ts` and its test.
- `apps/web/src/features/sites/siteTheme.ts` and
  `features/sites/hooks/useSiteTheme.ts`.

## The five facts this batch codes against

Measured, not remembered.

1. **There is no `@custom-variant dark` anywhere in the repo.** Under Tailwind
   4 the default `dark` variant therefore compiles to
   `@media (prefers-color-scheme: dark)`. The 45 `dark:` utility lines in TSX
   fire today for any user whose operating system is dark, against a `:root`
   that has no dark colors at all. The three `.dark` CSS blocks need a class
   nothing ever sets. Two mechanisms, neither connected.
2. **`:root` holds bare `H S% L%` triples**, and `@theme inline` wraps each one
   as `hsl(var(--x))`. `chartTheme.ts` wraps them the same way at runtime:
   `` `hsl(${raw})` ``. The triple format is load-bearing in three places, so
   the palette is DESIGNED in OKLch and SHIPPED as triples.
3. **`.dark` overrides four shadow tokens and nothing else.** No color token
   has a dark value. `--shadow-inset` and `--shadow-glow` have none either.
4. **`applySiteTheme` writes five properties as INLINE styles on
   `document.documentElement`**: `--primary`, `--ring`, `--secondary`,
   `--accent`, `--muted`. An inline style beats `[data-theme="dark"]`.
   `clampLightnessForWhiteText` only ever lowers lightness, and `--secondary`,
   `--accent` and `--muted` are written at hardcoded 95, 93 and 96 percent
   lightness.
5. **Four chart accessors and four divergent kind palettes exist.**
   `globals.css`,
   `lib/components/charts/chartTheme.ts`'s `CHART_TOKEN_FALLBACKS` (same
   values, hardcoded light), `SetVenn.FALLBACK_COLORS` (different hues) and
   `apps/web/src/lib/utils/chartTheme.ts`'s `CHART_COLORS`, a fourth accessor
   holding `hsl(var(--chart-N))` strings for the same eight tokens, for charts;
   `--kind-*`, `--kind-*-soft`/`-ring` (rgb values that do not match their own
   HSL siblings), `EditorHeader.KIND_BG` and `SmartMiniMap.MINIMAP_NODE_COLOR`
   for step kinds.

## Inherited constraints

- ASCII punctuation only, in CSS comments too.
- No type suppressions, no `as any`.
- `max-lines` 300 per TS file. `globals.css` is not a TS file and is exempt.
- No `useEffect`, `useMemo`, `useCallback` or `memo`.
- Components never call `fetch`.
- Gate ladder for every task:

```
cd /Users/ahmedmuharram/repos/pathfinder/apps/web
npx tsc --noEmit
npx eslint src/
node scripts/check-boundaries.mjs
node scripts/check-weak-assertions.mjs
npx vitest run <exact test files for this task>
```

## The palette, decided

Values are given as the `H S% L%` triples that ship. Each one carries its OKLch
in an ASCII comment, computed by the implementer with a throwaway script or by
hand and recorded in the report (no color library is installed: `culori` is
absent from `yarn.lock`, and this batch adds no dependency); the plan fixes the
HSL, the implementer records the OKLch beside it.

**The light neutrals change hue and nothing else.** Today they run 200 to 222;
they become a single 210-to-215 family so the paper reads as one ground. Every
lightness stays where it is, because `statusTokens.test.ts` passes today
against those grounds and a lighter or equal ground can only improve a
contrast ratio.

**The light status trio does not change.** `--destructive: 9 80% 37%`,
`--success: 142 50% 27%` and `--warning: 32 85% 28%` already carry AA on all
five surfaces, on their own 15 percent tints, and as white-on-solid. Repainting
them buys nothing and risks the one hard gate in the styles directory.

### Light, on bare `:root`

```
--background:            210 22% 98%    /* was 200 20% 97% */
--foreground:            215 42% 12%    /* was 222 47% 11% */
--card:                  0 0% 100%
--card-foreground:       215 42% 12%
--popover:               0 0% 100%
--popover-foreground:    215 42% 12%
--primary:               193 68% 35%    /* unchanged; the site theme overwrites it */
--primary-foreground:    0 0% 100%
--secondary:             210 22% 95%    /* was 200 25% 95% */
--secondary-foreground:  215 42% 12%
--muted:                 210 20% 95%    /* was 200 20% 95% */
--muted-foreground:      215 16% 40%    /* unchanged */
--accent:                210 22% 93%    /* was 200 25% 93% */
--accent-foreground:     215 42% 12%
--destructive:           9 80% 37%      /* unchanged */
--destructive-foreground: 0 0% 100%
--success:               142 50% 27%    /* unchanged */
--success-foreground:    0 0% 100%
--warning:               32 85% 28%     /* unchanged */
--warning-foreground:    0 0% 100%
--border:                212 20% 89%    /* was 200 20% 89% */
--input:                 212 20% 84%    /* was 200 20% 85% */
--ring:                  193 68% 42%    /* unchanged */
--sidebar:               210 22% 95%    /* was 200 25% 95% */
```

### Light chart series, replaced

The current set fails its own validator: `--chart-3` (amber, `38 92% 50%`)
sits above the lightness band, and `--chart-2`, `--chart-3` and `--chart-6`
are under 3:1 against the light ground. The new set holds one lightness band
and clears 3:1 on white.

```
--chart-1:        215 75% 45%   /* blue */
--chart-2:        160 65% 33%   /* green, darkened from 45% for 3:1 on white */
--chart-3:         28 85% 42%   /* burnt orange, replaces the out-of-band amber */
--chart-4:        355 70% 45%   /* crimson */
--chart-5:        275 55% 50%   /* violet */
--chart-6:        192 80% 33%   /* deep cyan, darkened from 50% */
--chart-positive: 160 65% 33%   /* equals --chart-2 */
--chart-negative: 355 70% 45%   /* equals --chart-4 */
```

### Dark, under `:root[data-theme="dark"]`, placed AFTER `:root`

```
--background:            215 28% 9%
--foreground:            210 20% 92%
--card:                  215 25% 12%
--card-foreground:       210 20% 92%
--popover:               215 25% 13%
--popover-foreground:    210 20% 92%
--primary:               193 65% 58%
--primary-foreground:    215 28% 9%
--secondary:             215 22% 16%
--secondary-foreground:  210 20% 92%
--muted:                 215 22% 15%
--muted-foreground:      215 15% 65%
--accent:                215 22% 18%
--accent-foreground:     210 20% 92%
--destructive:           6 75% 65%
--destructive-foreground: 215 28% 9%
--success:               142 45% 60%
--warning:                38 80% 62%
--success-foreground:    215 28% 9%
--warning-foreground:    215 28% 9%
--border:                215 20% 22%
--input:                 215 20% 26%
--ring:                  193 65% 55%
--sidebar:               215 26% 11%

--chart-1:        210 90% 70%
--chart-2:        160 55% 58%
--chart-3:         30 85% 62%
--chart-4:        355 80% 70%
--chart-5:        272 70% 74%
--chart-6:        190 70% 60%
--chart-positive: 160 55% 58%
--chart-negative: 355 80% 70%

--kind-leaf:      160 55% 58%
--kind-combine:   200 75% 65%
--kind-transform: 272 60% 68%
--kind-leaf-soft:      rgb(52 211 153 / 0.14)
--kind-leaf-ring:      rgb(52 211 153 / 0.38)
--kind-combine-soft:   rgb(56 189 248 / 0.14)
--kind-combine-ring:   rgb(56 189 248 / 0.38)
--kind-transform-soft: rgb(192 132 252 / 0.14)
--kind-transform-ring: rgb(192 132 252 / 0.38)

--shadow-card, --shadow-float, --shadow-composer, --shadow-composer-focus
    the four values the .dark block holds today, moved verbatim
--shadow-inset: inset 0 1px 1px rgb(0 0 0 / 0.25)
--shadow-glow:  0 0 20px rgb(255 255 255 / 0.06)
```

**Verified before shipping, by the implementer, not by this document.** The
dark status trio was chosen against `--background: 215 28% 9%` and computes to
roughly 5.9:1 for `--destructive`, 8.7:1 for `--success` and 9.5:1 for
`--warning`, with the 15 percent self-tint case tightest at about 4.9:1 for
`--destructive`. Those are estimates. Task A3's test is the authority: if a
value misses 4.5:1, move the lightness and record the change, do not lower the
threshold.

### The light `--kind-*` drift, fixed

`--kind-leaf` is `160 60% 45%` (about `#2eb888`) while `--kind-leaf-soft` is
`rgb(16 185 129)` (`#10b981`); `--kind-combine` is `200 80% 55%` (cyan-blue)
while `--kind-combine-soft` is `rgb(99 102 241)` (indigo). The soft and ring
variants are re-derived from their own HSL siblings so one step kind is one
color:

```
--kind-leaf-soft:      hsl(160 60% 45% / 0.10)
--kind-leaf-ring:      hsl(160 60% 45% / 0.30)
--kind-combine-soft:   hsl(200 80% 55% / 0.10)
--kind-combine-ring:   hsl(200 80% 55% / 0.30)
--kind-transform-soft: hsl(270 60% 55% / 0.10)
--kind-transform-ring: hsl(270 60% 55% / 0.30)
```

## Lead rulings at close

Where the batch as executed departs from the text of this card, the frozen
suites and the measured values decided:

- Dark `--destructive` ships at `6 75% 73%`, not `65%`: at 65 the token's own
  15 percent tint reads 3.80:1 over `--accent` and 4.16:1 over `--muted`; 73
  is the first lightness with margin (4.63:1). Hue and saturation held, the
  threshold untouched.
- `--kind-*-soft` and `--kind-*-ring` are `hsl(var(--kind-X) / a)` on both
  grounds (light 0.10/0.30, dark 0.14/0.38), not re-typed literals: the frozen
  theme module classifies an `rgb(...)` value as a color and an `hsl(...)` one
  as not, so the plan's two shapes would declare six dark colors with no light
  twin. Referencing the sibling token makes the drift the plan fixes
  impossible to reintroduce.
- The two `.specialist-rail-*` dark overrides are deleted rather than
  rewritten: both grounds read `hsl(var(--chart-1))` and `hsl(var(--chart-5))`,
  so a dark rule would set what the base rule already sets.
- `hsl(${raw})` cannot live in `chartTheme.ts` (the frozen assertion is
  `not.toContain("hsl(")`); `hslFromTriple` and `hslTriple` live in
  `lib/color/hsl.ts` beside `contrast.ts`, and `siteTheme.ts` formats through
  them.
- `statusTokens.test.ts` changed in one logical hunk: its private contrast
  functions became the import from `lib/color/contrast.ts`. Regex, first-match
  rule, thresholds and every assertion are byte-identical; the contrast math
  exists once with four importers (`statusTokens.test.ts`,
  `darkStatusTokens.test.ts`, `siteTheme.ts`, `siteTheme.test.ts`).
- The dead CSS beyond the keyframes went too, each name proven to have no
  consumer in `src/` or `e2e/`: the utilities `fade-up`, `message-fade-in`,
  `thinking-dot`, `composer-glow`, `subtle-lift` with their keyframes
  (`message-in`, `glow-pulse`), and the classes `.animate-shimmer`,
  `.warning-dash`, `.warning-group-node`, `.save-attention`, `.toast-animate`,
  `.toast-progress` with their keyframes (`shimmer`, `warning-dash`,
  `save-attention`, `toast-in-out`, `toast-progress`). Every keyframe left in
  the file has a referrer in the file.
- Five dead keyframes went, not three: `progress-pulse`, `slide-in-from-left`,
  `slide-in-from-right`, `slide-in-from-top`, `slide-in-from-bottom`, plus
  `pulse-subtle` and its `--animate-*` token, each proven unreferenced across
  `src/` and `e2e/`. The bare `slide-in-from-*-2` classes in `components/ui`
  are the animate plugin's vocabulary, not these keyframes; see the backlog
  item on the shadcn animation classes.
- "Validated" for the chart series means this card's own two criteria: one
  lightness band per ground (light L 33 to 50, dark L 58 to 74 in HSL) and at
  least 3:1 against that ground (measured minima 3.81 light, 6.08 dark), plus
  the AA pairs `darkStatusTokens.test.ts` asserts. The external dataviz
  validator the verifier ran (a skill script, not a repo gate) applies its own
  floors, a chroma floor of 0.10 (dark `--chart-6` reads 0.096), a 15 dE
  adjacent-hue floor (orange and crimson sit at 12.7) and a dark band of L
  0.48 to 0.67 in OKLch that would put every dark series below the level a
  dark ground needs for 3:1 with margin. Those floors are not adopted; the
  repo's gate is `chartTheme.test.ts` plus the two contrast suites.
- `components/ui/button.tsx` and `badge.tsx` lose `dark:bg-destructive/60`
  and `dark:focus-visible:ring-destructive/40`: the token carries both
  grounds, and a 60 percent destructive fill under the dark
  `--destructive-foreground` measures 3.55:1, under AA.
- Two lead edits after acceptance, outside the batch's own scope: the frozen
  EDA journey's "Open in EDA tab" navigation gets a 60 second bound on its
  `toHaveURL`, because a dev server compiles that route on its first request
  (37.8 s measured cold against a 15 s default, 5 s warm), and
  `globals.css` imports `tw-animate-css` so the vendored primitives'
  `animate-in`, `fade-in-0`, `zoom-in-95` and `slide-in-from-*-2` classes
  resolve; `src/styles/animatePlugin.test.ts` pins both the import position
  and the plugin's vocabulary.
- Six scrims, not four: `lib/components/Modal.tsx` and
  `features/settings/.../MemoryEditor.tsx` already read the token at 30
  percent and now sit at the one value, `bg-foreground/50`;
  `components/ui/__tests__/overlayTokens.test.tsx` scans every `.tsx` under
  `src/` for `bg-foreground/N` and refuses any N other than 50.
- `CHART_TOKEN_FALLBACKS` collapsing to one neutral made the "colors series by
  token order" chart tests vacuous; they now set distinct tokens on the
  document root, which also proves `readChartTokens` reads the document.

## Implementer A: the token layer, the variant, the theme-aware seams

### Files

**Modify**

- `apps/web/src/styles/globals.css`
- `apps/web/src/lib/components/charts/chartTheme.ts`
- `apps/web/src/lib/components/charts/chartTheme.test.ts`
- `apps/web/src/lib/components/charts/category.options.ts`
- `apps/web/src/lib/components/charts/scatter.options.ts`
- `apps/web/src/features/sites/siteTheme.ts`
- `apps/web/src/features/sites/siteTheme.test.ts`
- `apps/web/src/features/sites/hooks/useSiteTheme.ts`

**Create**

- `apps/web/src/styles/darkStatusTokens.test.ts`
- `apps/web/src/styles/tokenCompleteness.test.ts`

### Task A1: the two blocks and the custom variant

Red: `apps/web/src/styles/tokenCompleteness.test.ts`, this batch's own copy of
batch 0 task 0.7 items 1 to 6, written independently. It fails on the file as
it stands.

Green, in `globals.css`, in this order:

1. `@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));`
   immediately after the `@plugin` line. Every `dark:` utility in the app is
   now bound to the attribute instead of to the operating system.
2. `:root` keeps its position and gains the light values above, with an OKLch
   comment on each color.
3. A new `:root[data-theme="dark"] { ... }` block AFTER `:root`, with the dark
   values above. It must come after, or `statusTokens.test.ts`'s first-match
   regex silently starts measuring the dark palette.
4. The `.dark { ... }` block at line 170 is DELETED, its four shadow values
   moved into the dark block.
5. `.dark .specialist-rail-validate > *` and
   `.dark .specialist-rail-research > *` at lines 776 and 783 become
   `[data-theme="dark"] .specialist-rail-validate > *` and the same for
   research, and their four hardcoded rgb literals -
   `rgb(147 197 253)`, `rgb(216 180 254)` light, `rgb(30 64 175)`,
   `rgb(107 33 168)` dark - become `hsl(var(--chart-1))` and
   `hsl(var(--chart-5))` on both grounds, which is what they were reaching for.
6. `--animate-*` gains nothing. The dead `progress-pulse` keyframe (line 450)
   and the unreferenced `slide-in-from-left` and `slide-in-from-right` are
   deleted in this task: they are debt this change touches.

### Task A2: `chartTheme` reads the ground it is on

Red: `chartTheme.test.ts` gains cases: with `data-theme="dark"` on
`document.documentElement`, `readChartTokens()` returns the dark values; with
nothing defined, it returns fallbacks that are not the light palette hardcoded
a second time.

Green:

1. `CHART_TOKEN_FALLBACKS` stops being thirteen `hsl(...)` literals.
   `readChartTokens` reads `document.documentElement`; when a property is
   empty it falls back to `currentColor` for text roles and to a single
   neutral `hsl(0 0% 50%)` for series roles, and the ONE remaining literal is
   named `UNRESOLVED_SERIES_COLOR` with a comment saying it means the
   stylesheet did not load. A chart that paints grey is a visible bug; a chart
   that paints the light palette on a dark ground is an invisible one.
2. `category.options.ts` line 40 and `scatter.options.ts` line 21 stop
   carrying their own `"hsl(215 70% 50%)"` fallback and use
   `tokens.series[0] ?? UNRESOLVED_SERIES_COLOR`.
3. Batch 0 task 0.7 item 7 asserts `chartTheme.ts` contains no `hsl(` literal.
   `UNRESOLVED_SERIES_COLOR` therefore lives in its own module,
   `apps/web/src/lib/components/charts/unresolved.ts`, and `chartTheme.ts`
   imports it. Read the frozen assertion before writing, and satisfy it as
   written rather than arguing with it.

### Task A3: the dark WCAG gate

Red then green: `apps/web/src/styles/darkStatusTokens.test.ts` is
`statusTokens.test.ts`'s structure pointed at the dark block. It parses only
the `:root[data-theme="dark"]` block - slice the file at
`indexOf(':root[data-theme="dark"]')` before matching, so the two suites can
never read each other's palette - and asserts, for `--destructive`,
`--success` and `--warning`:

- 4.5:1 as text on `--card`, `--background`, `--sidebar`, `--muted` and
  `--accent`
- 4.5:1 on the token's own 15 percent tint over each of those five
- 4.5:1 for `--destructive-foreground` on the solid token, which on dark is a
  DARK foreground, not white. `statusTokens.test.ts` hardcodes `WHITE`; the
  dark suite reads the token's own `-foreground` instead.

The contrast math is duplicated three times in this repo already
(`statusTokens.test.ts`, `siteTheme.ts`, and now here). Extract it once into
`apps/web/src/lib/color/contrast.ts` and have all three import it, in this
task. Three copies of a WCAG calculation is how one of them drifts.

### Task A4: `applySiteTheme` learns the ground

Red: `siteTheme.test.ts` gains: given `data-theme="dark"` on the root,
`applySiteTheme("plasmodb")` writes a `--primary` whose lightness is ABOVE the
brand hex's, and `--secondary`, `--accent` and `--muted` at dark lightnesses,
and `--primary-foreground` is dark rather than white.

Green:

1. `clampLightnessForWhiteText` becomes `clampLightnessForForeground(h, s, l,
   foreground)`, which raises lightness when the foreground is dark and lowers
   it when the foreground is light, both until 4.6:1. It uses
   `lib/color/contrast.ts` from task A3.
2. `applySiteTheme` reads
   `document.documentElement.getAttribute("data-theme")` and picks the
   light constants (`${h} 25% 95%`, `${h} 25% 93%`, `${h} 20% 96%`) or the
   dark ones (`${h} 22% 16%`, `${h} 22% 18%`, `${h} 20% 15%`).
3. It also writes `--primary-foreground` now, which it does not today, so the
   button text follows the ground it was computed against.
4. `useSiteTheme` is left alone. PathFinder never flips the attribute, so a
   dependency on the theme would be dead code. Say so in the report rather
   than adding it.

## Implementer B: the consumers

### Files

**Modify** - the migration list, by cluster. The counts are from a direct
enumeration of the palette-shade utilities and the hex/rgb/hsl literals; the
`text-white` / `bg-black` class of literal was swept less systematically, so
Implementer B re-runs the scan for those before starting and reports the count
found.

**Cluster 1: amber that means warning (21 amber lines in 15 files, plus one
sky line and one yellow line that carry the same meaning).** `rg -n "amber-"`
over `src/**/*.{ts,tsx}` reports 23 lines in 17 files; the two not listed here
are `SupersededBadge.tsx:67` (batch 2 owns it) and `geneSetSourceConfig.ts:21`
(cluster 2 owns it). Every one becomes `text-warning`, `border-warning/40`,
`bg-warning/10` or `text-warning-foreground` as appropriate:

- `features/conversation/rail/LedgerContrasts.tsx:31,35`
- `features/analysis/components/ThresholdSweep/CategoricalPicker.tsx:40`
- `features/analysis/components/ThresholdSweep/SweepSummary.tsx:99`
- `features/settings/components/ModelCatalogModal.tsx:242`
  (`text-sky-500/80` becomes `text-primary/80`)
- `features/strategy/editor/RecoveryBanner.tsx:13`
- `features/strategy/editor/widgets/DatasetParam.tsx:177`
- `features/strategy/editor/widgets/FilterFacetedPicker.tsx:54`
- `features/strategy/editor/widgets/FilterParam.tsx:90`
- `features/strategy/editor/widgets/PhyleticProfileParam.tsx:202` (lines 195
  and 198 are green and red include/exclude marks: cluster 2)
- `features/strategy/graph/components/CanvasTopbar.tsx:260`
- `features/strategy/graph/components/CompactDisconnectedSection.tsx:40,42,49`
- `features/strategy/graph/components/nodes/NodeShell.tsx:99`
- `features/strategy/graph/components/nodes/ZeroResultHoverCard.tsx:27,37`
- `features/strategy/graph/components/OrphanNotice.tsx:25,39,50`
- `features/workbench/components/GeneChipInput.tsx:75` (`border-l-amber-500`,
  a chip state) and
  `features/workbench/components/GeneChipInput.integration.test.tsx:282`,
  which asserts that literal class name and is re-pointed in the same edit
- `features/workbench/components/OverlapModal.tsx:108` (`yellow-500`,
  `yellow-700`, `dark:text-yellow-400`: the same meaning under another name)

`LedgerContrasts.tsx:35`'s `text-amber-600/80` is an alpha-faded status text;
`statusTokens.test.ts`'s source lint bans that shape for token names and misses
it only because it is a literal. Once it becomes `text-warning/80` the lint
catches it, so it becomes `text-warning` with no alpha. Same for
`OrphanNotice.tsx:25`'s `text-amber-800/80`.

**Cluster 2: green and red that mean success and failure (24 lines, 11
files).** `text-success` and `text-destructive`, dropping every `dark:` twin,
because the token now carries both grounds:

- `features/workbench/components/panels/ConfidencePanel.tsx:43,44`
- `features/workbench/components/panels/EnsemblePanel.tsx:172`
- `features/workbench/components/panels/StepContributionPanel.tsx:19-22,101`
- `features/workbench/components/SaveControlSetForm.tsx:83`
- `features/workbench/components/VerificationResults.tsx:21`
- `features/workbench/components/CompareModal.tsx:79,81,85` (79 is blue and
  85 is orange; they are the same three-way legend and move with 81)
- `features/workbench/components/geneSetSourceConfig.ts:15,21,27,33,39`
- `features/strategy/editor/widgets/phyleticProfileLogic.ts:280,281`
- `features/strategy/editor/widgets/PhyleticProfileParam.tsx:195,198`
- `features/workbench/components/GeneChipInput.tsx:73` (`border-l-green-500`)
  and `features/workbench/components/GeneChipInput.integration.test.tsx:267`,
  which asserts that literal class name

`StepContributionPanel`'s `verdictColors` maps four verdicts onto four palette
pairs; it becomes `bg-success/15 text-success`, `bg-primary/15 text-primary`,
`bg-muted text-muted-foreground` and `bg-destructive/15 text-destructive`.

**Cluster 3: the other chart palettes.** `lib/components/SetVenn.tsx:14,22`
- `FALLBACK_COLORS` and its `"#2563eb"` - is deleted and replaced by
`readChartTokens().series` from task A2. `SetVenn` is the third copy of the
chart palette and the one with the wrong hues.
`apps/web/src/lib/utils/chartTheme.ts`'s `CHART_COLORS` is the fourth
accessor: eight `hsl(var(--chart-N))` strings naming the same tokens under
their own role names (`positive`, `negative`, `primary`, `secondary`,
`warning`, `destructive`, `purple`, `cyan`). It is routed through the one token
set too - the role names may stay, the values come from
`readChartTokens()` - so a chart drawn through it follows the ground like every
other chart, and there is one place a token name is written.

**Cluster 4: the step-kind palettes.**

- `features/strategy/editor/EditorHeader.tsx:30-32`'s `KIND_BG` becomes
  `bg-[hsl(var(--kind-leaf)/0.15)] text-foreground` and its two siblings.
- `features/strategy/graph/components/SmartMiniMap.tsx:8-11,19`'s `MINIMAP_NODE_COLOR` and
  its `"#94a3b8"` default read the kind tokens through `getComputedStyle`, in
  the same shape `chartTheme.readChartTokens` uses. Its
  `maskColor="rgba(0,0,0,0.1)"` at line 42 becomes
  `hsl(var(--foreground) / 0.1)`.

**Cluster 5: the ReactFlow canvas.**

- `lib/strategyGraph/deserialize.ts:167,170,177,179,180,199,200,203,206` - nine
  hexes in `deserializeStrategyToGraph`. They become token reads through one
  new helper in the same file that resolves `--border`, `--foreground`,
  `--card` and `--muted-foreground` once per call.
- `features/strategy/graph/components/StrategyGraphLayout.tsx:118`'s
  `colorMode="light"` becomes
  `colorMode={document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light"}`,
  read once at render. Line 124's `<Background color="#e2e8f0" />` becomes
  `hsl(var(--border))`.

**Cluster 6: the overlays and the white text.**

- `components/ui/alert-dialog.tsx:35` (`bg-black/50`),
  `components/ui/dialog.tsx:38` (`bg-black/70`),
  `components/ui/sheet.tsx:35` (`bg-black/50`) and
  `lib/components/ui/AlertDialog.tsx:25` (`bg-black/80`) become ONE value:
  `bg-foreground/50`. Four scrims for one concept is the bug; pick 50 percent
  and say so.
- `components/ui/badge.tsx:15` and `components/ui/button.tsx:14`'s `text-white`
  on the destructive variant become `text-destructive-foreground`, which the
  token already defines on both grounds.
- `components/ui/slider.tsx:56`'s `bg-white` thumb becomes `bg-card`.
- `app/components/TopBar.tsx` and `QuotaPill.tsx`, and
  `features/sites/components/SiteAuth.tsx` and `SitePicker.tsx`, sit on a site-brand photo
  and are DELIBERATELY white with a drop shadow. They are left alone, and the
  report says so with the reason. A rule that cannot name its exceptions gets
  applied where it does not belong.
- `features/strategy/graph/components/nodes/CombineNode.tsx:64,77`,
  `TransformNode.tsx:58`'s `border-white` become `border-card`.
  `nodes/MiniVenn.tsx:128-133`'s `fill="white"` / `fill="black"` are SVG
  luminance masks, not theme colors; leave them and say so.

**Cluster 7: the enrichment gradient.**
`features/analysis/components/enrichment-utils.ts:10-16`'s `pvalColor` computes an HSL
ramp from a hardcoded hue base of 220, and
`features/analysis/components/enrichment-utils.test.ts:89,93` pins its literal output - the only test in the
app that pins a color value. The ramp becomes an interpolation between
`--chart-1` and `--chart-4` read through the token layer, and the test's two
literals become assertions on the ENDPOINTS being the token values, read the
same way. `features/analysis/components/EnrichmentDotPlot.tsx:107`'s four-stop
`linear-gradient` becomes the same ramp.

### Task B1 to B7

One task per cluster, in that order, each red-green: the component's existing
test gains an assertion that the class is the token class, or a new test is
written when none exists. Cluster 3, 5 and 7 need real assertions on values,
not on class names, because they read tokens at runtime.

## Section close-outs

**A:**

- [ ] `cd apps/web && yarn format`
- [ ] `npx tsc --noEmit && npx eslint src/ && node scripts/check-boundaries.mjs && node scripts/check-weak-assertions.mjs && npx vitest run`
- [ ] `npx vitest run --config vitest.acceptance.config.ts`
- [ ] Report: the OKLch value computed for every token in both blocks, as a
  table; the measured contrast ratio for each of the six dark status pairs and
  the six dark tint pairs, with any value that had to move and its new
  lightness; confirmation that `statusTokens.test.ts` is UNCHANGED and still
  measures the light palette; zero-debt statement.

**B:**

- [ ] same ladder
- [ ] Report: the count of hardcoded literals before and after, by cluster; the
  re-run count for the `text-white` / `bg-black` class; every literal
  deliberately kept, with its reason; zero-debt statement.

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

1. **The dark block placed before `:root`.** `statusTokens.test.ts` then
   measures the dark palette and passes for the wrong reason. Check the byte
   offsets, not the visual order.
2. **`statusTokens.test.ts` modified.** It is not frozen, but it is the one
   WCAG gate on the light palette and this batch must not touch it. Any hunk in
   that file is a FAIL unless the batch report names it and justifies it.
3. **A token switched to `oklch()` or a full `hsl()` function.**
   `statusTokens.test.ts` throws, `@theme inline` double-wraps, and
   `chartTheme.ts` produces `hsl(oklch(...))`.
4. **`@custom-variant dark` missing, or bound to a class rather than the
   attribute.** Grep for it and read its body.
5. **A `.dark` selector still present** anywhere in `globals.css`.
6. **A color defined only in the dark block**, or only in the light block.
   Run batch 0's frozen `theme.acceptance.ts` and read its diff report, both
   directions.
7. **A `dark:` utility left in a component whose token now carries both
   grounds.** The cluster 2 files hold fifteen `dark:` twins and `src/` holds
   29 `dark:text-`, `dark:bg-` and `dark:border-` lines today; grep all three
   across `src/` and list every survivor with its reason.
8. **`CHART_TOKEN_FALLBACKS` still a hardcoded light palette**, or a new
   `hsl(` literal in `chartTheme.ts`. Batch 0 asserts the negative.
9. **`SetVenn.FALLBACK_COLORS` still present**, or
   `lib/utils/chartTheme.ts`'s `CHART_COLORS` still holding its own
   `hsl(var(--chart-N))` strings instead of reading the one token set.
10. **A fourth copy of the contrast math.** After task A3 there must be exactly
    one, in `lib/color/contrast.ts`, with three importers.
11. **`applySiteTheme` writing near-white constants on a dark ground.** Set the
    attribute, call it, read back the five properties, and check the
    lightnesses.
12. **`applySiteTheme` no longer writing `--primary-foreground`**, or writing
    white on a dark ground.
13. **A per-site brand color that no longer reaches a component.** Render a
    component that uses `bg-primary` after `applySiteTheme("plasmodb")` and
    assert the resolved value carries plasmodb's hue, 271 degrees or thereabouts
    from `#634697`.
14. **`--chart-3` still amber at `38 92% 50%`**, or any series token outside
    the chosen lightness band on its own ground.
15. **A chart series color under 3:1 against its own ground.** Run the dataviz
    validator over both sets and paste its output.
16. **`--kind-*-soft` still disagreeing with `--kind-*`.** Convert both to the
    same color space and compare.
17. **The four dialog scrims still divergent.**
18. **`colorMode="light"` still hardcoded** in `StrategyGraphLayout`.
19. **A thread testid moved.** The frozen thread and EDA suites are the gate;
    run both.
20. **A hardcoded color introduced by this batch.** Re-run the enumeration and
    diff the counts.
21. **A dead keyframe or `@utility` left behind**, or a live one deleted.
    `progress-pulse`, `slide-in-from-left` and `slide-in-from-right` are the
    three named as dead; confirm with `findReferences` before and after.
22. **Smart punctuation** in a CSS comment.
23. **`enrichment-utils.test.ts` weakened** to `toBeTruthy` rather than
    re-pointed at the token endpoints.

Mutation probes, three:

- Delete `--chart-3` from the dark block. Batch 0's `theme.acceptance.ts` must
  fail with a named difference.
- Change dark `--warning` to `38 80% 30%`. `darkStatusTokens.test.ts` must
  fail on the contrast assertion, not on a parse error.
- In `applySiteTheme`, remove the ground check so the light constants are
  always written. `siteTheme.test.ts`'s dark case must fail.

Report format, mandatory:

```
Batch 3 verification

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
statusTokens.test.ts unchanged  YES/NO

Per task
  A1 two blocks + variant   PASS/FAIL  <evidence>
  A2 chartTheme             PASS/FAIL
  A3 dark WCAG gate         PASS/FAIL
  A4 applySiteTheme         PASS/FAIL
  B1 amber cluster          PASS/FAIL  <n>/23
  B2 green-red cluster      PASS/FAIL  <n>/24
  B3 SetVenn + CHART_COLORS PASS/FAIL
  B4 kind palettes          PASS/FAIL
  B5 ReactFlow canvas       PASS/FAIL
  B6 overlays and white     PASS/FAIL
  B7 enrichment gradient    PASS/FAIL

Token table  (every token: light triple, light OKLch, dark triple, dark OKLch)

Contrast    (six dark status pairs and six dark tint pairs, measured ratio)

Hardcoded literals  (before, after, deliberately kept with reason)

Traps  (1 to 23, each CLEAN or the file:line that violates it)

Mutation probes  (each: the mutation, the killing test, or SURVIVED)

Definition of done
  zero debt            YES/NO  <what remains>
  adjacent reconciled  YES/NO  <what was missed>
  backlog item deleted YES/NO
  tests assert values  YES/NO
```

## Exit criteria

For the session lead to close batch 3:

1. Every gate green, verified by the lead's own run.
2. Every color token defined in `globals.css` has both a light value and a dark
   value, proven by batch 0's frozen `theme.acceptance.ts` passing unmodified.
3. `@custom-variant dark` is bound to `[data-theme="dark"]`, no `.dark`
   selector remains, and no `dark:` utility fires from the operating system.
4. PathFinder sets no `data-theme` attribute anywhere, and there is no theme
   toggle.
5. The eight chart tokens carry a validated set on each ground, and the dataviz
   validator's output for both is in the report.
6. `statusTokens.test.ts` is unchanged and still measures the light palette;
   `darkStatusTokens.test.ts` measures the dark one; the contrast math exists
   once.
7. `applySiteTheme` produces a legible brand primary on either ground and
   writes its own foreground, and a plasmodb brand color still reaches a
   component.
8. Every cluster is migrated, and every deliberately kept literal is named with
   its reason.
9. `docs/knowledge/backlog/chart-tokens-have-no-dark-mode-values.md` is deleted
   and its line removed from `backlog/index.md`.
10. The verifier's report shows all twenty-three traps CLEAN, three mutation
    probes killed, and "zero debt YES".
