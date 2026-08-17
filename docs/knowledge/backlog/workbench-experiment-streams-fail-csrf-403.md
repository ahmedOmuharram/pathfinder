---
type: Backlog Item
title: Workbench Evaluate, Batch, Benchmark, seed and threshold-sweep streams POST without X-Requested-With and are refused with 403
description: Run evaluation on a gene set shows "stream failed: 403"; the request is POST /api/v1/experiments with body but no X-Requested-With header, and the CSRF middleware refuses every state-changing request without it. Five stream callers share the omission; the task-event stream sends the header and works.
tags: [investigation, ui-run, workbench, experiments, csrf, streaming]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB Workbench)

**What I did.** Selected the 46-gene set, expanded Evaluate, added four positive controls
via "From Gene Set" (the 4-gene derived set), clicked Run evaluation.

**What I got.** Inline error "stream failed: 403".
`POST /api/v1/experiments → 403 {"detail":"Missing required X-Requested-With header"}`.
The request headers carried `accept: text/event-stream` and `content-type:
application/json` only.

**Why that is wrong.** Every experiment surface in the Workbench (Evaluate, Batch,
Benchmark), plus the seed stream and the threshold sweep, is unusable from the browser.
The error text tells the user nothing.

**Why it happens.** `platform/security.py` refuses any non-safe method without
`X-Requested-With`. `lib/api/http.ts` sets it for ordinary calls and
`useTaskEventStream.ts` passes it explicitly, but `lib/sse/typedEventStream.ts` does not
add it, and its five POST callers do not either:
`features/workbench/api/streaming.ts` (`createExperimentStream`,
`createBatchExperimentStream`, `createBenchmarkStream`), `lib/api/experiments.ts:58`
(seed stream), `lib/api/analysis.ts:115` (sweep). The `_proxy.ts` route only forwards the
header when present.

**Fix (to decide).** Set the header once in `streamTypedEvents` for non-GET methods (and
drop the per-caller copy in `useTaskEventStream`), and make the stream helper surface the
response body's `detail` in the thrown error. Add a jsdom test that asserts the header on a
POST stream.

**What you would get.** Run evaluation streams progress and completes.
