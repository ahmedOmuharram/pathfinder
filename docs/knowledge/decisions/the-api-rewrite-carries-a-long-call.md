---
type: Decision
title: The API rewrite carries a long call
description: Next caps a rewrite at 30 s and answers its own bare 500, which cut off the data purge; the cap is raised in next.config.ts rather than making the purge asynchronous or moving every long route to a route handler.
tags: [frontend, transport, nextjs, purge]
generated: { by: claude-code/opus-5, at: 2026-08-20T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-20T00:00:00Z }
status: stable
---

# What was decided

The browser reaches the API through the `/api/:path*` rewrite in
`apps/web/next.config.ts`. Next's proxy applies
`proxyTimeout || 30000` (`next/dist/server/lib/router-utils/proxy-request.js`),
and on expiry it sets `statusCode = 500` and ends the body with the 21 bytes
`Internal Server Error`. That answer carries none of the API's headers, so a
caller cannot tell it apart from an API fault.

`experimental.proxyTimeout` is set to 300000, above the longest legitimate API
call.

Measured: `DELETE /api/v1/user/data?deleteWdk=true` against 50 conversations
across 13 VEuPathDB sites returned that 500 at 30.03 s on four consecutive
attempts, with no `server: uvicorn` and no `x-request-id`, while the client
allowed 240 s. The API never got to answer. `Settings -> Data -> clear all data
including VEuPathDB strategies` is the same call from the browser.

# Why not make the purge asynchronous

A background job with a progress channel is the right shape for an operation
that can run for minutes, and it is a feature, not a timeout fix. It also would
not help the next long route. The cap is what turns a slow answer into a wrong
one, so the cap is what changed.

# Why not move long routes to Next route handlers

A route handler bypasses the rewrite: `POST /api/v1/experiments/seed` ran 128 s
through `app/api/v1/experiments/route.ts` in the same session that the purge was
cut off at 30 s. But a handler per long route is a second proxy implementation
that has to be kept in step with the first, and the routes that need it are not
known in advance.

# What this does not do

It does not make a purge fast. `_purge_wdk_strategies`
(`services/user_data.py`) parallelizes the deletes inside one site and walks the
sites one at a time, so wall-clock time grows with the number of sites the user
has strategies on. That is a separate measurement and a separate change.
