---
type: Backlog Item
title: "Add a step at the end" rebuilds the whole strategy from the frame's spec, so a parameter the user changed by hand in the editor is silently reverted
description: The user edited min_expression_percentile 80 -> 90 in the graph editor (step 1,456 -> 752, root 15 -> 7). The next chat turn ("add a P. vivax ortholog transform at the end") re-framed, rebuilt every step with new WDK ids, restored 80, and reported 16 orthologs without saying the hand edit was undone.
tags: [investigation, ui-run, build, editor, edit-strategy, data-loss, graph-ownership]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB, conversation 4f69357c)

**What I did.** With a built 3-step strategy, opened the editor and set the Su percentile
step's `min_expression_percentile` to 90 (saved: step 752, root 7; persisted revision
`daac9e0704b82659` with the parameter `"90"`). Then sent: "Now add a step at the end that
transforms the result into P. vivax P01 orthologs."

**What I got.** Intent `edit_strategy`; Frame "preserve the existing intersection of
c1_protease_text and c3_pf_su_gametocyte_expr, then apply c4_pvivax_orthology_transform";
build "Built 4 steps". Persisted after the turn: revision `a94b2a277ef8360e`, four steps
with **all new** ids and WDK step ids (`440116943, 440116953, 440116963, 440116973`, the
previous were `440116823/833/843`), `min_expression_percentile "80"`, counts 2,122 /
1,456 / 15 / 16. Reply: "Done - the strategy now ends with an ortholog transformation
step ... returns an estimated 16 P. vivax P01 orthologs." No mention of the percentile.

**Why that is wrong.** The user's own edit is undone without notice, and the number they
are given (16) is the count of a strategy they no longer have. The old WDK steps are
orphaned on the server. This is the "AI can only whole-graph-replace" gap from the graph
architecture review showing up as data loss.

**Why it happens.** An edit turn re-frames from the criteria the frame remembers (the
frame's spec still says 80) and the build materialises the frame's plan wholesale rather
than applying an operation (append a transform) to the live graph the editor wrote.
`get_live_strategy_state` was called and did carry `min_expression_percentile: "90"`, but
nothing forces the frame to start from it.

This is the residual risk that
[build_strategy is deliberately not revision-guarded](../decisions/build-strategy-is-not-revision-guarded.md)
records, measured live. The revision guard did not fire because the Lead read the current
revision first; the guard is not the gap, the frame's starting point is.

**Fix (to decide).** Edit turns must operate on the live graph: for an "add step" the
build should apply `appendTransform(rootStepId, ...)` to the current graph and leave the
other steps' WDK ids and parameters untouched; when a re-frame is unavoidable it must seed
from the live parameters and list any value it changes back. The generated graph
operations already exist and are unused (see the graph architecture review).

**What you would get.** 4 steps, only one new WDK step, `min_expression_percentile` still
90, root count computed on top of 7 (not 15).
