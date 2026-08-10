---
type: Backlog Item
title: WDK's "result not ready" sentinel is read as data
description: WDK answers 202 with a not-ready marker when a process query is still running. The transport accepts it as success, so the one condition WDK explicitly says to retry surfaces as a parse error or is discarded.
tags: [wdk-alignment, integrations, http, reliability]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# The defect

`_request_attempt` in `apps/api/src/pathfinder/integrations/veupathdb/_http.py` calls
`response.raise_for_status()` and then returns the parsed body. 202 is a success status, so
the sentinel body is handed to callers as though it were the report they asked for.

The upstream behavior that makes this a defect, with its pinned citations, is
[WDK-HTTP-003](../wdk/rules/auth-and-transport.md). The rule is currently `UNENFORCED`;
finishing this work is what would let it say `ENFORCED by <test>`.

# What a researcher actually sees

Two different symptoms depending on which call path is running, and neither one says
"not ready yet".

**A misattributed parse error, on the paths that produce gene counts.** Everything that
goes through `strategy_api/base.py:_standard_report` or `_searches.py:run_search_report`
validates into `WDKAnswer`, whose `meta` field is required. The sentinel has no `meta`, so
`validate_response` raises `DataParsingError` reading roughly "Unexpected WDK answer
response for step N: meta field required". That is loud, which is good, but it points at
the wrong thing: it reads as "WDK returned a shape our model does not expect", so the
natural next move is to go inspect the model rather than to wait and retry. The actual
meaning is that the result exists and is still being computed.

**Silence, on the one path that discards the return value.**
`services/strategies/sync.py` calls `run_step_report` for each configured report and
ignores what comes back. A sentinel there is swallowed whole and sync continues as though
the report had run.

# What this is not

Worth stating so nobody escalates it wrongly: on every path traced, this does **not**
produce a wrong gene count or a silent zero. `WDKAnswer.meta` being required is what
prevents that - the sentinel cannot validate into an answer with `totalCount` defaulting to
0. The cost is a retryable condition presented as a bug, plus one place where it vanishes.

# How to confirm

No live WDK needed. The unit tests in
`apps/api/src/pathfinder/tests/unit/integrations/veupathdb/` already drive `HTTPClient`
through an `httpx.AsyncBaseTransport` stub - `test_http_session_reinit.py` is the pattern.
Return `httpx.Response(202, json={"status": "accepted", "message": "WDK-DELAYED-RESULT"})`
and assert on what `_request_attempt` does with it. That test fails today.

Reproducing it against a live site is harder and not necessary: it needs a process query
whose WSF plugin has not finished, which is a race.

# Where to look, and the shape of the fix

`_http.py:_request_attempt` is where the 2xx is accepted, so that is the anchor. Two things
the fix should get right, both of which the reference client already does and neither of
which is obvious:

- **Match on the body shape, not on 202.** `wdk-client` decodes *every* ok response against
  the sentinel and throws on a match. Keying off the status code alone is narrower than
  upstream and will miss it if WDK ever returns the marker under a different 2xx.
- **Raise something named for what happened.** A distinct error meaning "the result is not
  ready" is the entire value here; converting it into another generic parse failure would
  leave the misattribution in place.

Per the repo's TDD rule the failing test comes first. Use a Pydantic model for the sentinel
rather than a `dict.get` chain.

# Anchor

`_request_attempt` in `integrations/veupathdb/_http.py`. Done when a 202 sentinel raises a
named not-ready error, a test asserts it, and
[WDK-HTTP-003](../wdk/rules/auth-and-transport.md) has been moved off `UNENFORCED` in the
same change.
