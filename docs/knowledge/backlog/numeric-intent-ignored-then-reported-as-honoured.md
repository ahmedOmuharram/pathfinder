---
type: Backlog Item
title: A numeric bound stated in the request is ignored, then reported as honoured
description: "Top 10 percent" resolved to WDK's default min_expression_percentile of 80 (the top 20 percent), and the reply told the scientist "percentile 80-100 (top 10%)". The resolution half is closed; the reporting half is what remains.
tags: [agents, parameters, correctness, verification]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
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
live). Resolution at the time read the criterion text with a tier of Python
rules, and those rules resolved options against a vocabulary; a bare number has
no vocabulary, so the param fell to `_scalar_default` and took WDK's 80. The
quantity in the criterion text was never read. That tier was deleted on
2026-08-17 ([one proposer, one validator](../decisions/one-proposer-one-validator.md)).

This is deliberate for numbers and correct as far as it goes -- see
[decisions/numeric-default-is-not-an-example.md](../decisions/numeric-default-is-not-an-example.md),
which established that a numeric `initialDisplayValue` is a real default rather
than an example. The gap is that a default must not outrank a number the user
actually stated.

# Why this one matters more than a wrong count

A wrong count is visible. This is a **plausible** result -- the intended genes, real
kinases, verification green -- that answers a subtly different question than the
one asked, and then asserts it answered the original. A scientist has no way to
catch it without re-deriving the parameters by hand.

# Two defects, not one

1. **Resolution.** A quantity stated in the criterion text should bind the
   numeric param it governs, or the param should come back to be read. Silently
   taking the default is the one option that must not happen.
2. **Reporting.** The reply asserted "(top 10%)" next to the value 80 without
   checking that the value means that. Verification compares counts; it does not
   compare the built parameters against the request.

Fixing only the first leaves the reporting free to mislabel the next parameter.

# The resolution half is closed

**Attribution.** The model now proposes a value or an explicit null for every
visible parameter of the search in one call, with all five numeric bounds, their
help text and their defaults in front of it. Deciding that "1.3" belongs to
`dn_ds_ratio_upper` rather than to one of the other four is a choice made with
the whole list in view, which is what no rule in our code could do. Measured on
the gold corpus: the proposer states 222 of 332 values, where the rules that
read the text bound 13.

**Suppression, for the case where the model stays silent.**
`param_dag._states_a_quantity` holds a numeric default back when the criterion
text states a quantity that is not that default **and** the search has exactly
one numeric slot. The param comes back in `ResolvedParams.unread`, whether or
not it is required, and `set_criterion` refuses the call with a retry that asks
for the stated value or for the criterion text to say why the default is right.
So a number the criterion states cannot be answered by a default in silence.

Two widenings of that guard were tried and both were refuted by the benchmark.
The numbers are from the pre-2026-08-17 scorer, so read them against their own
baseline row and not against any arm measured since:

| Rule | exact | wrong |
|---|---|---|
| baseline | 168 | 49 |
| hold back whenever the text states any number | 154 | 47 |
| ...only when the number differs from the default | 155 | 47 |
| **single numeric slot only** (kept) | **168** | **48** |
| ...treating `min_x`/`max_x` as one quantity | 161 | 48 |

The last row is the one that would have made the guard cover the search in the
symptom. It costs seven correct defaults and prevents no wrong value: on this
corpus the two ends of a range are where WDK's defaults are *most* often what a
human chose. The guard therefore still does not fire on a two-slot search, and
that is deliberate: on such a search the proposer is what reads the number.

# What remains: the reporting half

Nothing checks that a sentence about a parameter agrees with the value that was
bound. Verification compares counts. A reply may still write "(top 10%)" beside
the value 80, and the second defect in this item is exactly that sentence, not
the value behind it. Fixing resolution does not constrain the prose, and the
next mislabelled parameter will not be a percentile.

# Measured again in the browser, and the symptom did not reproduce

Two live turns on the search named above, which is the one this item was filed
from and which the guard does not cover:

| Request | `min_expression_percentile` | Reply |
|---|---|---|
| "top 10 percent" of trophozoite expression | **90** | "90-100th expression percentile (top 10%)" |
| "top 50 percent instead of the top 20 percent" | **50** | "percentile 50-100 (top 50%)" |

Both values are the arithmetically correct ones and both replies restate them
correctly. **The model produced these, not a rule**, which is now the design
rather than a gap: the guard needs a single numeric slot and this search has
two, so on this search the proposer is the whole mechanism. Two samples of a
model are evidence that the symptom is no longer easy to hit, not that it cannot
happen, and nothing yet compares the sentence with the value.

# Anchor

`_states_a_quantity` and `_scalar_default` in `services/catalog/param_dag.py`,
and the `unread` retry in `ai/tools/standalone/frame_spec.py:set_criterion`, for
resolution; guarded by
`tests/unit/services/catalog/test_stated_quantity_never_defaults.py` and
`TestAStatedQuantityLeftNullIsARetry` in
`tests/unit/ai/agents/test_frame_toolset.py`. The verification agent's
instructions for reporting. Done when a reply cannot restate a numeric parameter
with an interpretation the value does not support.
