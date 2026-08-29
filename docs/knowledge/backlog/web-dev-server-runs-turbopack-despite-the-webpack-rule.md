---
type: Backlog Item
title: The web dev container runs Turbopack although the e2e rule requires next dev --webpack
description: apps/web/package.json's dev script is `next dev` and the Dockerfile's dev target CMD is `yarn next dev -p 3000 -H 0.0.0.0`, so the e2e web container compiles routes on demand under Turbopack. CLAUDE.md and the batch-7 card both state that Turbopack buffers SSE and that `--webpack` is not optional. Measured on 2026-08-29: the EDA journeys, whose chat tails are fulfilled in the browser, pass, but the first navigation to /eda after a rebuild costs a cold compile that exceeds a 15 s expect. Whether Turbopack still buffers SSE on this Next version is unmeasured; the rule and the container disagree and one of them is wrong.
tags: [e2e, next, turbopack, docker]
generated: { by: claude-code/fable-5, at: 2026-08-29T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-29T00:00:00Z }
status: stable
---

**What I did.** Read `apps/web/package.json` and the `dev` target of the web
Dockerfile while running the batch-7 journeys, and watched a cold `/eda`
navigation fail a 15 s expect with Next Dev Tools showing "Rendering ...".

**What I got.** `"dev": "next dev"`, no `--webpack`; the same navigation
passes in under 5 s once the route is warm.

**Why that is wrong.** Either SSE-dependent specs are silently at risk (if the
buffering claim still holds) or the documented rule is stale and steers people
to the wrong flag; both cost time.

**Why it happens.** The rule was recorded on an earlier Next version and the
container command was never aligned with it.

**Fix.** Measure once: run a feature spec that streams a real mock chat turn
(not a browser-fulfilled tail) against the container as built, then with
`--webpack`. Keep whichever the measurement supports, align the script, the
Dockerfile and the two documents, and warm the EDA route in the e2e global
setup if the cold compile stays.

**What you would get.** One dev-server configuration that the docs describe
truthfully and that cold-start assertions can rely on.
