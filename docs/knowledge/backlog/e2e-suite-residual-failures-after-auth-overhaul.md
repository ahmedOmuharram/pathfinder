---
type: Backlog Item
title: 26 e2e specs still fail after the auth overhaul, in four clusters, while every worker turn succeeds
description: With the registered-login gate, the production web image, an isolated pathfinder_test database, the /open commit fix and the refresh no-op fix in place, the Playwright suite reaches 94 passed / 26 failed / 1 flaky (1.3 h). The worker completed 254 of 254 chat turns in that run, so the failures are client-side or spec-level. Clusters: strategy-build UI interactions (auto-build, execution-phase, strategy-edit family, dependent-strategy, and the five journeys that inherit them), deletion and dismissal flows (conversations delete, dismissed-strategies, insert-saved, user-data purge), durable-task live progress via the per-task SSE, and the never-executed unauthenticated-prompt spec whose dialog assertion does not match the DOM.
tags: [investigation, e2e, playwright, auth, tests]
generated: { by: claude-code/fable-5, at: 2026-08-20T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-20T00:00:00Z }
status: stable
---

# Investigation (full-suite runs, 2026-08-20)

**What I did.** Ran the full 133-spec Playwright suite against the containerized e2e
stack (mock provider, live WDK, `WDK_TEST_TOKEN` as the browser's `Authorization`
cookie) repeatedly while fixing what each run exposed: run 6 = production web image
(the dev-server image OOM-killed twice and hydration lagged behind clicks); run 8 =
isolated `pathfinder_test` database (the overlay had pointed at the dev database);
run 10 = after two product fixes found by trace forensics.

**What I got.** Run 6: 33 passed / 52 failed. Run 8: 36 passed. Run 10 (both fixes):
`94 passed / 26 failed / 1 flaky / 3 skipped / 9 did not run (1.3h)`, and the worker
log for the window shows `254 x "ended with status: Success"` chat turns, zero errors.
The two fixes, each measured from a trace: (1) `POST /api/v1/conversations/open`
returned its id before the session committed (the yield-dependency commits after the
response is sent), so the immediate sidebar listing omitted the new conversation -
open returned `beb136dc...` while the refreshed listing held only other ids; fixed by
an explicit commit in the route. (2) The app's on-load `POST /auth/refresh` re-minted
`pathfinder-auth` from the shared registered WDK token, silently switching every
worker onto one user - the listing request carried cookie `c147aef8` while /open
carried `f1e1a927` in one test; fixed by making refresh keep a valid existing session
(three unit tests).

**Why that is wrong.** A quarter of the suite cannot gate releases: the strategy-edit
family and every journey fail on waits for assistant output or AST state that the DOM
never shows, deletion flows fail waiting for a mock reply after a delete, the durable
progress card never advances from the per-task SSE in the spec's window, and the new
unauthenticated-prompt spec (`auth.spec.ts:6`) waits for `getByRole('dialog')` that
never appears - it had never been executed before this run.

**Why it happens.** Not established per cluster; the pipeline is healthy (every turn
succeeded), so the causes are client rendering, spec assumptions, or flow-specific
regressions from the login-gate batch, and each cluster needs its own trace read.

**Fix (to decide).** One task per cluster, each starting from a run-10 trace:
(1) strategy-build UI cluster incl. journeys; (2) deletion/dismissal cluster;
(3) durable per-task SSE progress; (4) `auth.spec.ts:6` dialog assertion vs the
forced-modal DOM (likely the spec, possibly a missing dialog role). Keep the e2e
stack recipe: production web image, `pathfinder_test`, api+worker with the e2e
overlay, `WDK_TEST_TOKEN` exported in the Playwright shell.

**What you would get.** A releasable e2e gate: 133 specs green or knowingly skipped,
on an isolated database, with the auth model the product now enforces.
