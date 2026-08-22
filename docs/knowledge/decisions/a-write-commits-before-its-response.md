---
type: Decision
title: A write the caller reads back commits before its response
description: The session dependency commits during teardown, after the response is sent, so a route whose caller refetches immediately commits in the route or the service; relying on the teardown, and moving the refetch later, were both rejected.
tags: [transport, persistence, postgres, testing]
generated: { by: claude-code/opus-5, at: 2026-08-20T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-20T00:00:00Z }
status: stable
---

# What was decided

`get_db_session` is a yield dependency, and FastAPI runs its teardown **after**
the response is sent. A route that returns a row the caller reads back in the
same tick therefore answers before its own write is visible to any other
session. Such a route commits explicitly, and the commit lives next to the
write.

Three write paths do it, and each names the caller that reads back:

- `POST /api/v1/conversations/open` commits in the route
  (`transport/http/routers/conversations/wdk_import.py`); the sidebar refetches
  the listing as soon as the new id arrives.
- `ConversationService.delete` and `ConversationService.restore` commit in the
  service (`services/conversations/service.py`), beside `dismiss`, `fork` and
  `duplicate`, which already did. `useDeleteWorkflow` invalidates the active
  and dismissed listings in the `finally` of the same call.

# Why not rely on the teardown

Because the race is not theoretical and it is not slow-machine-only. Three
integration tests hold a second session open and assert what it can see:
`tests/integration/services/conversations/test_delete_restore_durability.py`.
All three fail without the commit, on the first run, on a local database: the
row is deleted, dismissed or restored in the caller's transaction and unchanged
everywhere else.

The same class already cost one suite-wide outage. The listing refetch after
`/open` returned the other conversations and not the new one, and only a
production-speed client was fast enough to see it.

# Why not make the client refetch later

A delay would hide this instance and none of the next ones, and it puts the
correctness of a server write in the client's timing. A caller is allowed to
read its own write.

# How to test this class

An in-process HTTP transport cannot see it. `httpx.ASGITransport` awaits the
whole app call, dependency teardown included, before the test resumes, so the
commit has always happened by the time the test asserts. The test that works
calls the service directly and opens a **second** session from `session_maker`,
the pattern in `tests/integration/services/strategies/test_commit_integration.py`.

# What this does not do

It does not make every route commit. A route whose caller does not read back,
and a write that belongs to a longer unit of work, still commit in the
teardown. The rule is about the read-back, not about the write.
