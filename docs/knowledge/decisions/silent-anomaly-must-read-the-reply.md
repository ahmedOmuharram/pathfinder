---
type: Decision
title: A silent anomaly must read the reply
description: The devtool's silent_* detectors judged prose handling from structured ledger fields alone, so they fired on issues the Lead had explained.
tags: [devtools, diagnostics]
generated: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
status: stable
---

# The bug

`silent_constraint_violation` and `silent_zero` both claim the same thing: *the turn did not tell the user*. Both decided it from `ledger.constraints` and `ledger.build.zeroResultSteps` alone. Neither had ever seen the reply.

So a Lead that wrote "that intersection returned 0 genes, so there is no overlap" was still reported as silently failing. A debugger that cries wolf gets ignored, and this is the main tool for chat work.

# The fix

`diagnose` now takes `assistant_text`, and both detectors suppress themselves when the reply addresses the issue: for constraints, by naming the label or the requested value; for zeros, by a phrase reporting an empty result or by naming the step.

Capturing that text also closed a real gap. `RunCapture` was discarding `text-delta` entirely, so `transcript.md` listed tool calls and omitted the one thing the researcher actually read. The reply is now reassembled and written under a `## Reply` heading.

# Why matching prose is legitimate here, not a proxy

Text matching is usually a weak signal. It is the right one here because the anomaly's claim is *literally* about what the user-visible text says. Checking the text is a direct test of the claim rather than a stand-in for it.

`assistant_text` defaults to the empty string, which means "nothing was said". A run captured without reply text stays flagged rather than being quietly excused, so the failure mode is a false positive, never a false negative.

# Anchor

`devtools/diagnosis.py` (`_silent_constraint_violation`, `_silent_zero`, `_ZERO_RESULT_RE`) and `RunCapture.assistant_text`. Guarded by `TestConstraintHandledInProse` and `TestZeroHandledInProse` in `tests/unit/devtools/test_diagnosis.py`, and `TestReplyCapture` and `TestDiagnosisReadsTheReply` in `test_capture.py`.
