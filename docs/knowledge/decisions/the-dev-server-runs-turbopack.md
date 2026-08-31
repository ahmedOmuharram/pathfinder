---
type: Decision
title: The web dev server runs Turbopack, because Turbopack does not buffer SSE
description: Measured on Next 16.2.0 - a proxied text/event-stream reaches the client with its 300 ms gaps intact under Turbopack and under --webpack alike, so the "Turbopack buffers SSE, --webpack is not optional" rule is retired and the script, the Dockerfile and the documents all name plain `next dev`.
tags: [e2e, next, turbopack, sse, gates]
generated: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
status: stable
---

# What was decided

The web dev server runs Turbopack, which is Next 16's default. `--webpack` is
not passed anywhere: not in `apps/web/package.json`'s `dev` script, not in the
`dev` target of `apps/web/Dockerfile`, and not in any document.

# What was measured

An origin emitting five `text/event-stream` frames 300 ms apart was proxied
through `apps/web`'s `/api/:path*` rewrite by a Next 16.2.0 dev server, once as
the default and once with `--webpack`. Frame arrival, in seconds from the
request:

| hop | f0 | f1 | f2 | f3 | f4 |
|---|---|---|---|---|---|
| origin, no proxy | 0.075 | 0.379 | 0.690 | 0.994 | 1.302 |
| `next dev` (Turbopack) | 0.493 | 0.764 | 1.066 | 1.377 | 1.680 |
| `next dev --webpack` | 0.027 | 0.336 | 0.646 | 0.948 | 1.258 |

Both dev servers preserve the 300 ms gap. Neither holds the stream to its end.
Turbopack's first frame is later by the on-demand compile of the route, which
is a cold-start cost and not buffering: the four gaps after it are 0.271,
0.302, 0.311 and 0.303 s.

# What was rejected

Passing `--webpack`. The rule that required it was recorded on an earlier Next
version and no longer describes this one; keeping it would cost the default
bundler's start time (`Ready in 412ms` against `Ready in 470ms` here, and a
larger gap on a cold module graph) for a stream property both bundlers already
have.

# What follows

A cold-compile assertion is still a cold-compile assertion. A spec that
navigates to a route for the first time after a rebuild pays that compile under
either bundler, so a route an e2e journey enters cold is warmed in the global
setup rather than given a longer timeout.
