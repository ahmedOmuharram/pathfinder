---
type: Backlog Item
title: The worker's memory grows with every site it touches and is never released
description: After ~4 hours of e2e turns across five sites, the worker held 5.26 GiB (measured 2026-08-23); the API fully warm needs 6.5-7.2 GiB; on an 11.42 GiB Docker VM their sum OOM-killed the API. The growth is architectural, not a leak in the narrow sense - the embedding model plus per-site semantic indexes and catalogs load on demand per process and are never evicted. The container ceiling half has landed (worker and wdk-mcp both cap at 2g, see decisions/the-memory-ceilings-bound-the-growers-not-the-api.md), so a kill now lands on the process that grew. What remains is eviction - an LRU over a memory budget, or moving every per-site index into one process - because a 2 GiB worker still dies after two or three sites.
tags: [worker, memory, infra, embeddings]
generated: { by: claude-code/fable-5, at: 2026-08-23T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-24T00:00:00Z }
status: stable
---

**What I did.** Ran e2e journeys across plasmodb, cryptodb, fungidb, tritrypdb
and toxodb through the worker for ~4 hours, then read `docker stats` and
`docker compose ps -a`.

**What I got.** `pathfinder-worker-1 mem=5.262GiB / 11.42GiB` and
`pathfinder-api-1 mem=3.805GiB` (mid-rewarm; 6.5-7.2 GiB fully warm), with
`api Exited (137)` at 17:26:45 - the kernel OOM-killed the API while the
worker kept its 5 GiB. Two build-turn measurements taken across that window
read 389.9s and 1039.4s and were worthless. After `docker compose restart
worker`: `mem=43.49MiB`.

**Why that is wrong.** The API dies for the worker's appetite, and it dies
silently under load - a researcher's turn fails, the UI shows the startup
gate, and any measurement running at the time is corrupted without saying so.
An MCP client is told nothing either: the process dies inside the call, so the
client waits out its own read timeout - 300 s by default, and 600 s for a
client that honours the enrichment budget - before it fails.

**Why it happens.** Each chat turn on a new site loads that site's catalog and
semantic index into the worker process (plus the embedding model itself), and
nothing evicts: memory is monotone in the number of distinct sites touched.

**Fix.** The ceiling is in place: `mem_limit: 2g` on `worker` and on
`wdk-mcp`, so exhaustion kills the container that grew and it restarts clean.
What is left is eviction, and a second symptom now shows why: a `wdk-mcp`
call that names a site whose cached catalog has expired rebuilds that
catalog inside the call, passes 2 GiB, and the container restarts without
answering (measured 2026-08-24 on toxodb and cryptodb; the same build peaked
at 2.977 GiB under a 3 GiB ceiling and at 3.269 GiB under a 6 GiB one,
answering after 6.4 and 7.6 minutes). Either
direction fixes both: LRU eviction of per-site indexes over a configured
budget, or one process holding every index and serving the rest over MCP
(the fork the MCP execution plan records as decision point 4).

**What you would get.** A worker whose memory is bounded by policy rather
than by a kill, an MCP call that answers on a stale-cache site, and load
measurements that mean something.
