---
type: Backlog Item
title: A cold api process spends about 73 minutes encoding semantic indexes before uvicorn binds
description: Measured during the batch B/C review (2026-08-25): after a force-recreate with cold disk caches, the api preloaded 14 sites of catalog plus semantic-index encoding for about 73 minutes before the server bound; a second pass with warm caches was minutes. Until the bind, the container reports healthy-then-unhealthy states that mislead compose dependents, dev-login answers 502 through the web proxy, and every e2e or devtools run stalls. Related items cover the memory ceiling and /health/live slowness; this one is the serial cold-start cost itself. Fix directions: persist encoded indexes across recreates (the delta embedding cache exists for embeddings; extend to the encoded index), bind uvicorn before warm-up completes and gate readiness per site, or parallelize the per-site encoding.
tags: [infra, startup, embeddings, availability]
generated: { by: claude-code/fable-5, at: 2026-08-25T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-25T00:00:00Z }
status: stable
---

**What I did.** Timed the api container from preload start to uvicorn bind
after a force-recreate whose build had just exhausted the docker VM disk
(caches cold), during the batch B/C review.

**What I got.** About 73 minutes of serial per-site catalog and
semantic-index work before the server bound; the following recreate with
warm caches bound in minutes.

**Why that is wrong.** An hour-plus cold start turns every image rebuild
into an outage window: compose dependents mis-start, the web proxy serves
502, and any measurement or review that touches the stack stalls behind it.

**Why it happens.** Warm-up encodes every site's semantic index in process,
serially, before the server binds, and the encoded result does not persist
across recreates.

**Fix.** Persist the encoded indexes across recreates, or bind before
warm-up and gate readiness per site, or parallelize the encoding.

**What you would get.** Rebuilds that cost minutes, not an outage window.
