---
type: Decision
title: NUL is rejected at the ASGI boundary
description: Three simpler designs were tried and each provably fails; the working guard is pure ASGI middleware with a prefilter confirmed against the parsed body.
tags: [transport, postgres, security]
generated: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
status: stable
---

# The bug

PostgreSQL text cannot hold NUL (0x00). Any NUL that reached a query raised `asyncpg.CharacterNotInRepertoireError` mid-statement and the caller got a **500** for input that is simply unstorable. Only `siteId` was guarded, by an `AfterValidator`, so every new free-text filter rediscovered the crash. `/api/v1/control-sets?tags=%00` was live.

# Three designs that do not work

Each was tried and measured, not reasoned about. Recorded because each looks correct until you run it.

1. **A per-parameter validator.** This is what existed. It is whack-a-mole by construction: it guards the parameter someone remembered, and the next filter added is unguarded again.

2. **An exception handler mapping the driver error to 422.** Cannot work. A body value is only written at `session.commit()`, which FastAPI runs during **dependency teardown, after the response**, where exception handlers no longer apply. Also, the outermost exception is the generic `sqlalchemy.exc.DBAPIError`, so a handler broad enough to catch this would swallow connection failures too.

3. **A raw byte scan of the request body.** Finds nothing. JSON carries NUL as the escape `\u0000`; a literal 0x00 byte is invalid JSON and never arrives.

# What works

`RejectNullBytesMiddleware` in `platform/security.py`, as **pure ASGI** rather than `@app.middleware("http")`, because the body must be drained and replayed to the app through a wrapped `receive`.

It rejects NUL in the URL path, in any query parameter (key or value), and in a JSON body, with a 422.

The body check is a two-stage test, and both stages are load-bearing:

- **Prefilter** on the bytes `\u0000` or a raw 0x00. Cheap, and skips the parse for every normal request.
- **Confirm** against `json.loads`, because those same six bytes also spell a legitimate escaped backslash. Without the confirm, a researcher typing a Windows-style path gets a spurious 422.

Only JSON bodies are read. FastAPI already buffers those in full to parse them, so this adds no peak memory.

# Placement

Registered alongside `csrf_middleware`, outside CORS, matching the existing convention in that file. Starlette's `add_middleware` inserts at position 0, so the last registered runs outermost.

# Anchor

`platform/security.py`. Guarded by `tests/integration/transport/test_null_byte_rejection.py` (URL, body, and the escaped-backslash false positive) and `tests/unit/platform/test_null_byte_guard.py` (nested dicts, lists, keys, malformed JSON).
