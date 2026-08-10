---
type: Backlog Item
title: No way for a user to authorise defaults
description: Mostly resolved by fixing numeric defaults; what remains is genuinely ambiguous choices, where a user's explicit permission to guess still has no mechanism.
tags: [agents, frame, parameters, ergonomics]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# Most of this was a bug, and it is fixed

Filed as "FRAME leaves 9 open slots even when told to use defaults". Diagnosis found the number was mostly a defect, not a policy gap: five of seven slots were numeric bounds whose WDK-declared defaults were being discarded. See [a number's initial value is a default](../decisions/numeric-default-is-not-an-example.md). That criterion now resolves with zero questions.

The earlier 7-vs-9 comparison was also unsound -- run-to-run variance, measured on turns that crashed before the Lead could ask anything.

# What is genuinely left

Two slots on the DeRisi microarray criterion: `min_expression_percentile` and `samples_percentile_generic`. These are real choices that change the result, and WDK offers no default. A researcher who says "pick something sensible" is giving permission to proceed, and there is still no mechanism that hears it.

# The constraint on any such mechanism

It must not apply to contrast pairs. `_contrast_open_slot` surfaces an unspecified half of a reference/comparison pair because defaulting both halves to "all samples" is a degenerate all-vs-all contrast that returns zero DE genes. There is no safe default there, and an authorisation to guess must not override it.

So the design has two classes: slots where the resolver has ranked candidates and taking the top one is a defensible assumption, and slots where any guess is wrong. Only the first is eligible.

# Suggested shape

When the user authorises defaults, fill the eligible class from the resolver's best candidate and record each as an assumed constraint, so the ledger shows it and the user can override. Leave the rest as questions and say why.

# Anchor

`_open_slot` and `_contrast_open_slot` in `services/catalog/param_dag.py`. Done when a goal carrying an explicit defaults instruction reaches `ready_to_build` without asking about anything that has a defensible default.
