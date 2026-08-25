---
type: Backlog Item
title: The first chat POST of a fresh test process pays the PIGuard model load against a 5 s enqueue ceiling, so the failing test floats
description: In a full integration run (2 failed, 431 passed), the golden SSE snapshot test failed on its enqueue wait; standalone under load the same test failed in 13.86 s and standalone idle it passed; test_durable_turn failed only when it was the first chat POST of its process (1 failed, 5 passed, 70.97 s under a concurrent unit run). The dispatcher awaits the prompt-injection scan before deferring the turn, and the scanner lazily builds an onnxruntime InferenceSession on the process's first scan, which under load exceeds the 5.0 s wait_until_chat_turn_deferred ceiling. Production warms the scanner during readiness; the test app fixture never runs readiness. Fix: warm the scanner once per test process in the app fixture (mirroring readiness), or gate the first-scan cost out of the enqueue path.
tags: [tests, flake, piguard, dispatcher]
generated: { by: claude-code/fable-5, at: 2026-08-24T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-24T00:00:00Z }
status: stable
---

**What I did.** Ran the api integration suite whole, then the two red files
standalone, idle and under a concurrent unit-suite run (2026-08-23).

**What I got.** Whole suite: 2 failed, 431 passed; the golden SSE snapshot
test (the run's first chat POST) timed out waiting for the turn to enqueue,
while `test_durable_turn` passed later in the same warm process. Standalone
under load, `test_durable_turn.py` returned 1 failed, 5 passed in 70.97 s,
and only its first test failed. The golden test standalone failed in
13.86 s under load and passed idle.

**Why that is wrong.** Zero tolerance for flaky tests: the red floats to
whichever test happens to be its process's first chat POST, so a suite
failure points at an innocent test and a real regression can hide behind
"that one is just slow".

**Why it happens.** `dispatcher.py` awaits `scan_user_input` before
deferring the turn; `PIGuardScanner` lazily builds an onnxruntime
`InferenceSession` on the process's first scan (`piguard_enabled` defaults
true, and a plain prompt misses the approval whitelist). Under load that
first build exceeds the 5.0 s `wait_until_chat_turn_deferred` ceiling.
Production warms the scanner during readiness; the test app fixture never
runs readiness.

**Fix.** Warm the scanner once per test process in the app fixture, the
same way readiness does in production; alternatively move the first-scan
cost out of the enqueue path. A related margin: `test_optimize_params_impl`
asserts a 1.2 s bound that measured 1.42 s under the same load.

**What you would get.** An integration suite whose reds mean the code under
test regressed, on a loaded machine as well as an idle one.
