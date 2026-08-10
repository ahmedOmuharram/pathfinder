---
type: Backlog Item
title: A numeric bound stated in the request is ignored, then reported as honoured
description: "Top 10 percent" resolved to WDK's default min_expression_percentile of 80 (the top 20 percent), and the reply told the scientist "percentile 80-100 (top 10%)".
tags: [agents, parameters, correctness, verification]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# Symptom

A live PlasmoDB turn asked for genes "in the top 10 percent of expression during
the trophozoite stage". The strategy built and verification passed. The reply
read:

> **DeRisi 3D7 Smoothed expression:** percentile **80-100** (top 10%)

80-100 is the top **20** percent. The sentence contradicts itself and nothing in
the pipeline noticed.

# Root cause

`min_expression_percentile` has `initialDisplayValue: "80"` on WDK (confirmed
live). Tier-2 intent mapping (`map_intent_to_value`) resolves vocabulary options
by rule and embedding; a bare number has no vocabulary, so the param fell to
`_scalar_default` and took WDK's 80. The quantity in the criterion text was
never read.

This is deliberate for numbers and correct as far as it goes -- see
[decisions/numeric-default-is-not-an-example.md](../decisions/numeric-default-is-not-an-example.md),
which established that a numeric `initialDisplayValue` is a real default rather
than an example. The gap is that a default must not outrank a number the user
actually stated.

# Why this one matters more than a wrong count

A wrong count is visible. This is a **plausible** result -- 20 genes, real
kinases, verification green -- that answers a subtly different question than the
one asked, and then asserts it answered the original. A scientist has no way to
catch it without re-deriving the parameters by hand.

# Two defects, not one

1. **Resolution.** A quantity stated in the criterion text should bind the
   numeric param it governs, or the param should become an open slot. Silently
   taking the default is the one option that must not happen.
2. **Reporting.** The reply asserted "(top 10%)" next to the value 80 without
   checking that the value means that. Verification compares counts; it does not
   compare the built parameters against the request.

Fixing only the first leaves the reporting free to mislabel the next parameter.

# Anchor

`map_intent_to_value` / `_scalar_default` in `services/catalog/param_dag.py` for
resolution. The verification agent's instructions for reporting. Done when
"top 10 percent" produces `min_expression_percentile = 90` (or an open slot),
and when a reply cannot restate a numeric parameter with an interpretation the
value does not support.
