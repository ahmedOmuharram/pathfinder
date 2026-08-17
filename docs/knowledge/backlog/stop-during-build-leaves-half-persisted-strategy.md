---
type: Backlog Item
title: Stopping a turn during build persists a strategy with no record type and no WDK ids, and the editor then fails with a raw 422
description: The build phase writes the local plan (recordType "", wdkStepId null) before it pushes to WDK. A Stop between the two leaves that half-state on disk; the compact panel shows "..." for every count and the full editor's step-counts request returns 422 MISSING_RECORD_TYPE, shown to the user as "HTTP 422 Unprocessable Content".
tags: [investigation, ui-run, build, editor, cancellation, persistence]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB)

**What I did.** Sent the moderate protease/gametocyte prompt in a fresh conversation. When
the transcript showed the `build` card as `started` (declarative:no-llm), pressed Stop.
Reloaded the tab, opened the Strategy panel, then clicked Open (full editor).

**What I got.** `GET /api/v1/conversations/<id>` returned a 5-step strategy with
`recordType: null` at the top and `recordType: ""`, `wdkStepId: null`, `estimatedSize: null`
on every step, `wdkStrategyId: null`, `strategyRevision: a1de30e2c9261a84`. The compact
panel rendered `...` for all five counts. The editor issued
`POST /api/v1/conversations/step-counts` and got
`{"status":422,"code":"VALIDATION_ERROR","errors":[{"path":"recordType","message":"Record type is required","code":"MISSING_RECORD_TYPE"}]}`;
the UI showed a red toast "HTTP 422 Unprocessable Content" and every node read
`? results`. The same conversation after a *completed* build (turn 2) had
`recordType: "transcript"` and WDK ids on every step.

**Why that is wrong.** The user sees a strategy that looks built and cannot be counted,
opened, or trusted, and the only message is a transport status code. There is no way in the
UI to recover the counts short of asking the model for another turn.

**Why it happens.** The build phase persists the local plan first and fills record type and
WDK ids only when the push to WDK completes; `StrategyValidator.validate` then refuses the
plan the editor sends because `recordType` is empty
(`domain/strategy/validate.py:MISSING_RECORD_TYPE`), and the editor renders the
`ValidationError` title rather than the field message.

**Fix (to decide).** Either persist the plan only after the WDK push (one write, no
half-state), or persist it with the record type the frame already knows (`transcript`) and
mark the strategy `unsynced` so the editor computes counts through the plan endpoint. In
both cases the editor's error path should show the field message
("Record type is required") not the HTTP status. Also: the `build` phase card stays
`started` forever after a Stop; it should resolve to `cancelled`.

**What you would get.** After a Stop during build the panel either shows the plan with live
counts (unsynced) or shows nothing built yet, and the transcript's build card says
`cancelled`.
