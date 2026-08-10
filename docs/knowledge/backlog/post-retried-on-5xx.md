---
type: Backlog Item
title: Non-idempotent POSTs are retried on 5xx and on timeout
description: The WDK transport retries every request up to three times regardless of verb, so a proxy 502 or a timeout after WDK has already committed a step or strategy creates duplicates.
tags: [wdk-alignment, integrations, http, reliability]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# The defect

`_request_attempt` in `apps/api/src/pathfinder/integrations/veupathdb/_http.py` carries a
tenacity decorator that retries on `TimeoutException`, `ConnectError` and
`HTTPStatusError`, up to three attempts. The 4xx/5xx split inside the method is deliberate:
4xx becomes a `WDKError` immediately, and 5xx is re-raised specifically so tenacity retries
it.

Nothing in that path looks at the HTTP verb. `_request` is shared by `get`, `post`, `put`,
`patch` and `delete`, so the retry applies to creates as readily as to reads.

Two of those creates are not idempotent:

- `POST /users/{userId}/steps` - `strategy_api/steps.py:create_step`, `create_combined_step`,
  `create_transform_step`
- `POST /users/{userId}/strategies` - `strategy_api/strategies.py:create_strategy`,
  `copy_strategy`

Each returns a fresh `{id}` per call. A second attempt is a second object.

# Why this is reachable rather than theoretical

Every verification site fronts WDK with a proxy - responses from plasmodb.org and
toxodb.org both carry `Server: nginx/1.26.1`. A proxy returns 502 and 504 on its own, after
the request has already been passed upstream and possibly committed. `TimeoutException` is
the same story with no status at all: the write may well have landed.

So the failure needs no WDK bug. It needs one slow step creation behind a proxy, which is
ordinary on a large search.

# What a researcher actually sees

Orphaned steps and duplicate strategies, not wrong numbers. Only the id from the final
successful attempt is wired into the step tree, so the earlier committed steps are left
unreferenced, and duplicate `create_strategy` calls leave extra entries in the user's
strategy list. Clutter, wasted WDK writes, and confusing history.

Being exact about the blast radius, because the ranking matters: on the paths traced this
does **not** silently change a gene count. The duplicates are unreferenced rather than
wired into the tree. It is ranked below
[the delayed-result sentinel](delayed-result-sentinel-unhandled.md) for that reason - but
it is ranked as a real item rather than tidiness because the retry is verb-blind *by
construction*, so every non-idempotent POST added to this client from now on inherits it
silently. That is the part that gets worse over time.

# How to confirm

Unit level, no live WDK. Drive `HTTPClient` through an `httpx.AsyncBaseTransport` stub that
returns 502 twice and then 200 - `test_http_session_reinit.py` in
`apps/api/src/pathfinder/tests/unit/integrations/veupathdb/` is the established pattern for
that stub - and count the requests the transport actually received for a `post`. Today it
is three.

# Where to look

`_request_attempt` and `_request` in `integrations/veupathdb/_http.py`. The decision to
make is narrower than it looks: WDK offers no idempotency key, so the choices are to stop
retrying non-idempotent verbs, or to keep retrying and reconcile afterwards. Do not weaken
retry for GET, which is the case the decorator was added for and is genuinely safe.

Worth checking during the fix: whether `copy_strategy` and `create_step` have any existing
caller that already tolerates duplicates, which would change the reconciliation option's
cost.

# Anchor

The `@retry` decorator on `_request_attempt` in `integrations/veupathdb/_http.py`. Done
when a repeated 502 against a `post` issues one upstream write rather than three, and a
test asserts the count.
