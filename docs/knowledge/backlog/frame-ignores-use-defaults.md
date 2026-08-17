---
type: Backlog Item
title: No way for a user to authorise defaults
description: Mostly resolved by fixing numeric defaults; what remains is genuinely ambiguous choices, where a user's explicit permission to guess still has no mechanism.
tags: [agents, frame, parameters, ergonomics]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Most of this was a bug, and it is fixed

Filed as "FRAME leaves 9 open slots even when told to use defaults". Diagnosis found the number was mostly a defect, not a policy gap: five of seven slots were numeric bounds whose WDK-declared defaults were being discarded. See [a number's initial value is a default](../decisions/numeric-default-is-not-an-example.md). That criterion now resolves with zero questions.

The earlier 7-vs-9 comparison was also unsound -- run-to-run variance, measured on turns that crashed before the Lead could ask anything.

# What is genuinely left

Two slots on the DeRisi microarray criterion: `min_expression_percentile` and `samples_percentile_generic`. These are real choices that change the result, and WDK offers no default. A researcher who says "pick something sensible" is giving permission to proceed, and there is still no mechanism that hears it.

# The constraint on any such mechanism

It must not apply to contrast pairs. `_contrast_open_slot` surfaces an unspecified half of a reference/comparison pair because defaulting both halves to "all samples" is a degenerate all-vs-all contrast that returns zero DE genes. There is no safe default there, and an authorisation to guess must not override it.

So the design has two classes: slots where a defensible assumption exists, and slots where any guess is wrong. Only the first is eligible.

# Suggested shape

When the user authorises defaults, fill the eligible class and record each as an assumed constraint, so the ledger shows it and the user can override. Leave the rest as questions and say why.

The mechanism this was drafted against is gone: there is no ranking resolver to take a top candidate from ([one proposer, one validator](../decisions/one-proposer-one-validator.md)). What fills these slots now is the model, from the sheet, in the `set_criterion` call itself - which is what the browser runs below show. So the work left here is the recording half, not the filling half.

# Measured again in the browser: the two named slots now fill

The criterion in "What is genuinely left" was re-run live with an explicit
defaults instruction. Both slots filled and nothing was asked:
`min_expression_percentile` took 90 for "top 10 percent", and
`samples_percentile_generic` took the 14 samples covering 17-30 hours for
"trophozoite". Three further turns carrying the same instruction on other
searches also asked nothing. The reply named the defaults it chose, including
the hidden `channel` parameter.

So the behaviour in the "done when" holds. What is still unverified is the
second half of the suggested shape: that each assumed value is recorded as a
constraint the user can see and override, rather than only narrated in prose.

# Anchor

`_open_slot` and `_contrast_open_slot` in `services/catalog/param_dag.py`. Done when a goal carrying an explicit defaults instruction reaches `ready_to_build` without asking about anything that has a defensible default.
