---
type: Backlog Item
title: A client that walks away from search_example_plans leaves the work running, and three of them kill the wdk-mcp container
description: The call embeds every public strategy of a site and takes 21 s warm, 50 s cold. A client read timeout does not stop it, so three abandoned calls run concurrently inside the 2g ceiling and the kernel kills the process. Any client can do this; no credential is needed beyond one that reads.
tags: [mcp, memory, cancellation, availability, conformance]
generated: { by: claude-code/opus-5, at: 2026-08-25T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-25T00:00:00Z }
status: stable
---

# What I did

Ran the conformance suite against the served endpoint with a 5 second call
budget and `search_example_plans` named as the tool to drive past it:

```
pytest --pyargs mcp_conformance --mcp-endpoint http://localhost:8100/mcp \
  --mcp-slow-tool search_example_plans --mcp-max-call-seconds 5 ...
```

Family 3 calls it twice and family 5 once, each on a 5 second client timeout.
Measured beforehand, the same call answers in 22.06 s, 22.25 s and 21.10 s
against a warm plasmodb, and 48.09 s and 53.07 s against a cold one.

# What I got

The run ended in 28 s with every family failing, because the server was gone.
The container log stops mid-call and restarts eight seconds later:

```
00:26:08 Processing request of type CallToolRequest
         onnxruntime cpuid_info warning: Unknown CPU vendor
         INFO:     Started server process [1]
00:26:16 Application startup complete.
```

No shutdown line, `RestartCount` 1 under `restart: unless-stopped`, and
`mem_limit: 2g` on the service.

# Why that's wrong

The client timeout is the only thing the caller controls, and using it takes the
server down for every other caller. A gene-page assistant that sets a short
budget on a slow tool - which is exactly what a careful client does - is
indistinguishable from an attack. It also means the deployment's own admission
record cannot settle family 5: the three timeout checks are skipped in
`test_conformance_ours.py` because running them kills the server under test.

# Why it happens

`search_example_plans` in `apps/api/src/pathfinder/mcp/server.py` lists a site's
public strategies and embeds each one through `embed_text`. A streamable-HTTP
client that stops reading sends `notifications/cancelled`, and nothing in the
tool observes it: the embedding loop runs to completion holding its allocations.
Three of those overlap inside the 2g ceiling the memory decision set.

# Fix

Two parts, in this order.

1. Make the work cancellable: the embedding loop yields to the event loop
   between strategies, so a cancelled request raises inside it rather than
   running to the end. Verify with two overlapping calls against a warm site and
   the container's memory read before and after.
2. Bound the concurrency: one embedding pass at a time per site, so that a
   second caller queues rather than doubling the allocation.

Then delete the three timeout entries from `UNSETTLED_CHECKS` in
`apps/api/src/pathfinder/tests/integration/mcp/test_conformance_ours.py`, name
`search_example_plans` as `--mcp-slow-tool` again with a 5 second budget, and
the admission record's family 5 goes from one check to four.

# What you'd get

A client that abandons the call frees the server's memory with it. Three
abandoned calls leave the container serving. The admission record settles the
budget claim it currently reports as unsettled.
