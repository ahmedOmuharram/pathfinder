---
type: Backlog Item
title: The chart color tokens have no dark-mode values, and one fails the lightness band
description: apps/web/src/styles/globals.css defines --chart-1..6 and --chart-positive/negative once, and its .dark block overrides shadows only, so every chart (SetVenn and the batch-5 EDA charts) paints the light palette on the dark ground. The batch-5 dataviz validator also fails --chart-3 (amber, L 0.77) on the lightness band and warns on three slots under 3:1 contrast on light. Found 2026-08-28; a palette decision that repaints every existing consumer, so it is the lead's, not a batch's.
tags: [frontend, design, charts, tokens]
generated: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
status: stable
---

**What I did.** Read `apps/web/src/styles/globals.css` for the `--chart-*`
tokens while building the EDA chart theme, and ran the dataviz palette
validator over the token values.

**What I got.** Six series tokens plus `--chart-positive`/`--chart-negative`
defined on `:root` only; the `.dark` block redefines shadows and nothing
chart-related. Validator: CVD PASS, normal-vision floor PASS, chroma PASS,
lightness band FAIL on `--chart-3` (L 0.77), contrast WARN (under 3:1) on
`--chart-2`, `--chart-3`, `--chart-6` against the light ground.

**Why that is wrong.** A dark-mode reader sees light-tuned series colors on a
dark ground with no contrast check ever having been run for that pairing, and
the amber slot reads as a highlight rather than a series.

**Why it happens.** The tokens predate dark mode's chart consumers; nothing
forced a dark set when `.dark` was added.

**Fix (to decide).** Add a `.dark` set for the eight chart tokens validated
against the dark ground, and move `--chart-3` inside the lightness band; then
re-run the validator for both grounds and record the values in
`lib/components/charts/chartTheme.ts`'s test as the pinned palette. Every
chart consumer repaints, so do it once, deliberately.

**What you would get.** One validated palette per ground, and charts that are
legible in both themes without per-chart color overrides.
